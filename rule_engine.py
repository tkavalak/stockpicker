"""In-process rule evaluation for the market data POC."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, TypedDict

from alert_email import send_alert_email

PRICE_SPIKE_5M_THRESHOLD_PCT = 0.5
FIVE_MINUTES_MS = 5 * 60 * 1000


class MarketEvent(TypedDict):
    symbol: str
    event_type: str
    price: float
    volume: float
    timestamp: int


@dataclass(frozen=True)
class RuleFire:
    rule_name: str
    measured_value: float
    threshold: float


_price_history: dict[str, Deque[tuple[int, float]]] = defaultdict(deque)


def _parse_event(event: dict[str, Any]) -> MarketEvent:
    return {
        "symbol": str(event["symbol"]).upper(),
        "event_type": str(event["event_type"]),
        "price": float(event["price"]),
        "volume": float(event.get("volume") or 0),
        "timestamp": int(event["timestamp"]),
    }


def _normalize_timestamp(timestamp: int) -> int:
    """Polygon timestamps may be seconds, ms, or ns — normalize to milliseconds."""
    if timestamp > 1_000_000_000_000_000:
        return timestamp // 1_000_000
    if timestamp > 1_000_000_000_000:
        return timestamp
    return timestamp * 1000


def _price_at_or_before(
    history: Deque[tuple[int, float]], target_ms: int
) -> float | None:
    ref: float | None = None
    for ts, price in history:
        if ts <= target_ms:
            ref = price
        else:
            break
    return ref


def _evaluate_price_spike_5m(market_event: MarketEvent) -> RuleFire | None:
    symbol = market_event["symbol"]
    price = market_event["price"]
    timestamp_ms = _normalize_timestamp(market_event["timestamp"])
    history = _price_history[symbol]

    target_ms = timestamp_ms - FIVE_MINUTES_MS
    ref_price = _price_at_or_before(history, target_ms)
    if ref_price is None or ref_price == 0:
        return None

    pct_change = ((price - ref_price) / ref_price) * 100.0
    if pct_change > PRICE_SPIKE_5M_THRESHOLD_PCT:
        return RuleFire(
            rule_name="PRICE_SPIKE_5M",
            measured_value=pct_change,
            threshold=PRICE_SPIKE_5M_THRESHOLD_PCT,
        )
    return None


def _record_event(market_event: MarketEvent) -> None:
    symbol = market_event["symbol"]
    price = market_event["price"]
    timestamp_ms = _normalize_timestamp(market_event["timestamp"])

    price_history = _price_history[symbol]
    price_history.append((timestamp_ms, price))
    cutoff = timestamp_ms - FIVE_MINUTES_MS
    while price_history and price_history[0][0] < cutoff:
        price_history.popleft()


def evaluate_rules(event: dict[str, Any]) -> list[str]:
    """
    Evaluate hardcoded movement rules for a parsed market event.

    Expected keys: symbol, event_type, price, volume, timestamp.
    Returns fired rule names and logs each fire to stdout.
    """
    market_event = _parse_event(event)
    fires: list[RuleFire] = []

    price_fire = _evaluate_price_spike_5m(market_event)
    if price_fire:
        fires.append(price_fire)

    _record_event(market_event)

    for fire in fires:
        print(
            f"ALERT symbol={market_event['symbol']} rule={fire.rule_name} "
            f"measured={fire.measured_value:.4f} threshold={fire.threshold} "
            f"movement_type={fire.rule_name} timestamp={market_event['timestamp']}",
            flush=True,
        )
        send_alert_email(
            market_event["symbol"],
            fire.rule_name,
            fire.measured_value,
            fire.threshold,
            timestamp=market_event["timestamp"],
        )

    return [fire.rule_name for fire in fires]
