"""Per-symbol rolling windows — Redis (prod) or in-memory (local)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Protocol

import redis

from market_event_processor.models import PRICE_HISTORY_RETENTION_MS

logger = logging.getLogger(__name__)

KEY_PREFIX = "mep"


@dataclass
class SymbolWindow:
    prices: list[tuple[int, float]] = field(default_factory=list)
    volumes: list[float] = field(default_factory=list)


class WindowStore(Protocol):
    def ping(self) -> bool: ...

    def get_window(self, symbol: str) -> SymbolWindow: ...

    def save_window(self, symbol: str, window: SymbolWindow) -> None: ...


class InMemoryWindowStore:
    """Local fallback when Redis is not configured."""

    def __init__(self) -> None:
        self._windows: dict[str, SymbolWindow] = {}

    def ping(self) -> bool:
        return True

    def get_window(self, symbol: str) -> SymbolWindow:
        return self._windows.get(symbol.upper(), SymbolWindow())

    def save_window(self, symbol: str, window: SymbolWindow) -> None:
        self._windows[symbol.upper()] = window


class RedisWindowStore:
    def __init__(
        self,
        *,
        host: str,
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        socket_timeout: float = 2.0,
        client: redis.Redis | None = None,
    ) -> None:
        self._client = client or redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password or None,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )

    def ping(self) -> bool:
        return bool(self._client.ping())

    def _prices_key(self, symbol: str) -> str:
        return f"{KEY_PREFIX}:{symbol.upper()}:prices"

    def _volumes_key(self, symbol: str) -> str:
        return f"{KEY_PREFIX}:{symbol.upper()}:volumes"

    def get_window(self, symbol: str) -> SymbolWindow:
        sym = symbol.upper()
        prices_raw = self._client.get(self._prices_key(sym))
        volumes_raw = self._client.get(self._volumes_key(sym))
        prices: list[tuple[int, float]] = []
        volumes: list[float] = []
        if prices_raw:
            loaded = json.loads(prices_raw)
            prices = [(int(p[0]), float(p[1])) for p in loaded]
        if volumes_raw:
            volumes = [float(v) for v in json.loads(volumes_raw)]
        return SymbolWindow(prices=prices, volumes=volumes)

    def save_window(self, symbol: str, window: SymbolWindow) -> None:
        sym = symbol.upper()
        pipe = self._client.pipeline()
        pipe.set(
            self._prices_key(sym),
            json.dumps([[ts, price] for ts, price in window.prices]),
        )
        pipe.set(self._volumes_key(sym), json.dumps(window.volumes))
        pipe.execute()


def trim_price_history(
    prices: list[tuple[int, float]], *, now_ms: int
) -> list[tuple[int, float]]:
    cutoff = now_ms - PRICE_HISTORY_RETENTION_MS
    return [(ts, p) for ts, p in prices if ts >= cutoff]


def append_price(
    prices: list[tuple[int, float]], *, ts_ms: int, price: float
) -> list[tuple[int, float]]:
    updated = trim_price_history(prices, now_ms=ts_ms)
    updated.append((ts_ms, price))
    return updated


def append_volume(
    volumes: list[float], volume: float, *, max_len: int
) -> list[float]:
    if volume <= 0:
        return volumes
    updated = list(volumes)
    updated.append(volume)
    if len(updated) > max_len:
        updated = updated[-max_len:]
    return updated


def build_window_store() -> WindowStore:
    if os.environ.get("REDIS_USE_MEMORY", "").lower() in ("1", "true", "yes"):
        logger.warning("Using in-memory window store (REDIS_USE_MEMORY)")
        return InMemoryWindowStore()

    host = os.environ.get("REDIS_HOST", "").strip()
    if not host:
        logger.warning(
            "REDIS_HOST not set; using in-memory window store for local dev"
        )
        return InMemoryWindowStore()

    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None
    return RedisWindowStore(host=host, port=port, password=password)
