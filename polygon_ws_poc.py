#!/usr/bin/env python3
"""Minimal Polygon.io WebSocket POC — trades and per-second aggregates to stdout."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Iterable


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

from polygon.websocket import WebSocketClient
from polygon.websocket.models import EquityAgg, EquityTrade, Feed, WebSocketMessage

from rule_engine import evaluate_rules

RECONNECT_DELAY_SEC = 5
MAX_RECONNECT_ATTEMPTS = 1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def parse_watched_symbols() -> list[str]:
    raw = os.environ.get("WATCHED_SYMBOLS", "").strip()
    if not raw:
        raise ValueError(
            "WATCHED_SYMBOLS must be set (comma-separated tickers, e.g. AAPL,MSFT,NVDA)"
        )
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def build_subscriptions(symbols: Iterable[str]) -> list[str]:
    return [f"A.{symbol}" for symbol in symbols]


def to_market_event(msg: WebSocketMessage) -> dict | None:
    if isinstance(msg, EquityTrade):
        if msg.symbol is None or msg.price is None or msg.timestamp is None:
            return None
        return {
            "symbol": msg.symbol,
            "event_type": "trade",
            "price": msg.price,
            "volume": float(msg.size or 0),
            "timestamp": msg.timestamp,
        }
    if isinstance(msg, EquityAgg):
        if msg.symbol is None or msg.close is None or msg.end_timestamp is None:
            return None
        return {
            "symbol": msg.symbol,
            "event_type": "aggregate",
            "price": msg.close,
            "volume": float(msg.volume or 0),
            "timestamp": msg.end_timestamp,
        }
    return None


def print_event(event: dict) -> None:
    print(
        f"symbol={event['symbol']} event_type={event['event_type']} "
        f"price={event['price']} volume={event['volume']} "
        f"timestamp={event['timestamp']}",
        flush=True,
    )


async def handle_messages(msgs: list[WebSocketMessage]) -> None:
    for msg in msgs:
        event = to_market_event(msg)
        if event is None:
            continue
        print_event(event)
        evaluate_rules(event)


async def run_once(api_key: str, subscriptions: list[str]) -> None:
    feed_name = os.environ.get("POLYGON_WS_FEED", "Delayed")
    feed = Feed[feed_name]
    client = WebSocketClient(
        api_key=api_key,
        feed=feed,
        subscriptions=subscriptions,
        max_reconnects=0,
    )
    await client.connect(handle_messages)


async def main() -> None:
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        raise ValueError("POLYGON_API_KEY must be set")

    symbols = parse_watched_symbols()
    subscriptions = build_subscriptions(symbols)
    logger.info("Watching %s (%d subscriptions)", ", ".join(symbols), len(subscriptions))

    for attempt in range(MAX_RECONNECT_ATTEMPTS + 1):
        try:
            await run_once(api_key, subscriptions)
            return
        except Exception as exc:
            if attempt >= MAX_RECONNECT_ATTEMPTS:
                logger.error("Stream failed after reconnect attempt: %s", exc)
                raise
            logger.warning("Market data stream disconnected: %s", exc)
            logger.info(
                "Reconnecting in %d seconds (attempt %d of %d)",
                RECONNECT_DELAY_SEC,
                attempt + 1,
                MAX_RECONNECT_ATTEMPTS,
            )
            await asyncio.sleep(RECONNECT_DELAY_SEC)


if __name__ == "__main__":
    load_dotenv()
    try:
        asyncio.run(main())
    except (ValueError, KeyboardInterrupt) as exc:
        if isinstance(exc, ValueError):
            logger.error("%s", exc)
            sys.exit(1)
        logger.info("Stopped by user")
