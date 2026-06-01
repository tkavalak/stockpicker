"""Polygon.io WebSocket connection lifecycle and event ingestion."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Iterable

from polygon.websocket import WebSocketClient
from polygon.websocket.models import Feed, WebSocketMessage

from polygon_streamer.models import to_market_event_message
from polygon_streamer.pubsub_publisher import PubSubPublisher
from polygon_streamer.reconnect import (
    STABLE_SESSION_SEC,
    STREAM_UNAVAILABLE_NOTIFY_SEC,
    is_policy_violation,
    reconnect_delay_seconds,
)

logger = logging.getLogger(__name__)


def parse_watched_symbols(raw: str) -> list[str]:
    if not raw.strip():
        raise ValueError("WATCHED_SYMBOLS must be set")
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def build_subscriptions(symbols: Iterable[str]) -> list[str]:
    """Per-second aggregates only (A.*). Trade feeds (T.*) require a higher Polygon plan."""
    return [f"A.{symbol}" for symbol in symbols]


def parse_polygon_feed(raw: str | None = None) -> Feed:
    """Resolve Polygon WebSocket feed; default Delayed for basic plans."""
    name = (raw or os.environ.get("POLYGON_WS_FEED", "Delayed")).strip()
    try:
        return Feed[name]
    except KeyError as exc:
        valid = ", ".join(sorted(member.name for member in Feed))
        raise ValueError(f"Unknown POLYGON_WS_FEED {name!r}; expected one of: {valid}") from exc


def polygon_log_events_enabled() -> bool:
    return os.environ.get("POLYGON_LOG_EVENTS", "").strip().lower() in ("1", "true", "yes")


class PolygonStreamListener:
    def __init__(
        self,
        api_key: str,
        symbols: list[str],
        publisher: PubSubPublisher,
        *,
        feed: Feed | None = None,
    ) -> None:
        self._api_key = api_key
        self._symbols = symbols
        self._feed = feed or parse_polygon_feed()
        self._subscriptions = build_subscriptions(symbols)
        self._publisher = publisher
        self._connected = False
        self._connecting = False
        self._in_cooldown = False
        self._consecutive_unstable = 0
        self._disconnected_at: float | None = None
        self._stream_unavailable_notified = False
        self._stop = asyncio.Event()
        self._connection_lock = asyncio.Lock()
        self._last_policy_violation = False
        self._log_events = polygon_log_events_enabled()

    @property
    def connected(self) -> bool:
        return self._connected and not self._in_cooldown

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def subscriptions(self) -> list[str]:
        return list(self._subscriptions)

    @property
    def disconnected_seconds(self) -> float | None:
        if self._disconnected_at is None:
            return None
        return time.monotonic() - self._disconnected_at

    def request_stop(self) -> None:
        self._stop.set()

    def _mark_connected(self) -> None:
        self._connected = True
        self._in_cooldown = False
        self._disconnected_at = None
        self._stream_unavailable_notified = False
        logger.info(
            "Polygon WebSocket connected (1 session, %d subscriptions); watching %s via %s",
            len(self._subscriptions),
            ", ".join(self._symbols),
            self._feed.name,
        )

    def _mark_disconnected(self) -> None:
        if self._connected:
            logger.warning("Polygon WebSocket disconnected")
        self._connected = False
        if self._disconnected_at is None:
            self._disconnected_at = time.monotonic()

    def _check_stream_unavailable_notification(self) -> None:
        if self._connected or self._stream_unavailable_notified:
            return
        elapsed = self.disconnected_seconds
        if elapsed is not None and elapsed >= STREAM_UNAVAILABLE_NOTIFY_SEC:
            logger.error(
                "STREAM_UNAVAILABLE: market data monitoring interrupted for %.0fs "
                "(symbols: %s). REQ-RMA-007.3",
                elapsed,
                ", ".join(self._symbols),
            )
            self._stream_unavailable_notified = True

    async def _sleep_or_stop(self, seconds: float) -> bool:
        """Wait up to `seconds`. Returns True if stop was requested."""
        if seconds <= 0:
            return self._stop.is_set()
        self._in_cooldown = True
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._in_cooldown = False

    async def _handle_messages(self, msgs: list[WebSocketMessage]) -> None:
        for msg in msgs:
            event = to_market_event_message(msg)
            if event is None:
                if self._log_events:
                    logger.info("Polygon message ignored (unsupported type): %s", type(msg).__name__)
                continue
            if self._log_events:
                logger.info(
                    "Polygon event symbol=%s type=%s price=%s volume=%s raw=%s",
                    event.symbol,
                    event.event_type,
                    event.price,
                    event.volume,
                    event.raw_payload,
                )
            try:
                self._publisher.publish(event)
            except Exception as exc:
                logger.error(
                    "Failed to publish event symbol=%s type=%s: %s",
                    event.symbol,
                    event.event_type,
                    exc,
                )

    async def _run_connection(self) -> tuple[bool, str | None]:
        """
        Open one WebSocket session. Returns (stable_session, error_message).
        Only one session at a time (lock + _connecting guard).
        """
        if self._connecting:
            logger.warning("Skipping overlapping WebSocket connect (session already active)")
            return False, "overlapping connect skipped"

        async with self._connection_lock:
            if self._connecting:
                return False, "overlapping connect skipped"
            self._connecting = True
            session_started = time.monotonic()
            error_message: str | None = None
            client = WebSocketClient(
                api_key=self._api_key,
                feed=self._feed,
                subscriptions=self._subscriptions,
                max_reconnects=0,
                verbose=self._log_events,
            )
            self._mark_connected()
            try:
                await client.connect(self._handle_messages)
            except Exception as exc:
                error_message = str(exc)
                logger.warning("WebSocket session ended: %s", exc)
            finally:
                self._mark_disconnected()
                self._connecting = False

        stable = (time.monotonic() - session_started) >= STABLE_SESSION_SEC
        return stable, error_message

    async def run(self) -> None:
        first_session = True
        while not self._stop.is_set():
            if not first_session:
                delay = reconnect_delay_seconds(
                    max(1, self._consecutive_unstable),
                    policy_violation=self._last_policy_violation,
                )
                logger.info(
                    "Waiting %.1fs before reconnect (unstable_sessions=%d, policy_violation=%s)",
                    delay,
                    self._consecutive_unstable,
                    self._last_policy_violation,
                )
                if await self._sleep_or_stop(delay):
                    return

            first_session = False
            self._last_policy_violation = False

            stable, error_message = await self._run_connection()
            if self._stop.is_set():
                return

            if error_message and is_policy_violation(error_message):
                self._last_policy_violation = True
                logger.warning(
                    "Polygon policy violation (1008) — ensure only one streamer uses this "
                    "API key (stop local pipeline if Cloud Run is deployed)"
                )

            if stable:
                self._consecutive_unstable = 0
            else:
                self._consecutive_unstable += 1

            self._check_stream_unavailable_notification()
