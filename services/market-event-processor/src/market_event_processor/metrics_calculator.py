"""Compute enriched metrics from rolling price/volume windows."""

from __future__ import annotations

import math
import os

from market_event_processor.models import (
    FIVE_MINUTES_MS,
    ONE_MINUTE_MS,
    EnrichedMarketEvent,
    RawMarketEvent,
    timestamp_ms_from_ns,
)
from market_event_processor.window_store import (
    SymbolWindow,
    WindowStore,
    append_price,
    append_volume,
)


def _rolling_window_size() -> int:
    return int(os.environ.get("ROLLING_WINDOW_SIZE", "20"))


def _price_at_or_before(
    prices: list[tuple[int, float]], target_ms: int
) -> float | None:
    ref: float | None = None
    for ts, price in prices:
        if ts <= target_ms:
            ref = price
        else:
            break
    return ref


def _pct_change(current: float, reference: float | None) -> float | None:
    if reference is None or reference == 0:
        return None
    return ((current - reference) / reference) * 100.0


def _volatility_score(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    mean = sum(prices) / len(prices)
    if mean <= 0:
        return None
    variance = sum((p - mean) ** 2 for p in prices) / len(prices)
    stdev = math.sqrt(variance)
    return min(1.0, stdev / mean)


class MetricsCalculator:
    def __init__(self, store: WindowStore) -> None:
        self._store = store
        self._window_size = _rolling_window_size()

    @property
    def store(self) -> WindowStore:
        return self._store

    def enrich(self, raw: RawMarketEvent) -> EnrichedMarketEvent:
        """Compute metrics from prior window state, then persist the new event."""
        window = self._store.get_window(raw.symbol)
        ts_ms = timestamp_ms_from_ns(raw.timestamp_ns)

        pct_change_1m = _pct_change(
            raw.price, _price_at_or_before(window.prices, ts_ms - ONE_MINUTE_MS)
        )
        pct_change_5m = _pct_change(
            raw.price, _price_at_or_before(window.prices, ts_ms - FIVE_MINUTES_MS)
        )

        avg_volume_20: float | None = None
        volume_ratio: float | None = None
        if window.volumes:
            avg_volume_20 = sum(window.volumes) / len(window.volumes)
            if avg_volume_20 > 0 and raw.volume > 0:
                volume_ratio = raw.volume / avg_volume_20

        recent_prices = [p for _, p in window.prices[-self._window_size :]]
        volatility_score = _volatility_score(recent_prices)

        updated = SymbolWindow(
            prices=append_price(window.prices, ts_ms=ts_ms, price=raw.price),
            volumes=append_volume(
                window.volumes, raw.volume, max_len=self._window_size
            ),
        )
        self._store.save_window(raw.symbol, updated)

        return EnrichedMarketEvent(
            symbol=raw.symbol,
            event_type=raw.event_type,
            price=raw.price,
            volume=raw.volume,
            timestamp_ns=raw.timestamp_ns,
            raw_payload=raw.raw_payload,
            pct_change_1m=pct_change_1m,
            pct_change_5m=pct_change_5m,
            avg_volume_20=avg_volume_20,
            volume_ratio=volume_ratio,
            volatility_score=volatility_score,
        )
