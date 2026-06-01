"""SignalAgent — local heuristic pattern analysis (no I/O)."""

from __future__ import annotations

import os

from agentic_ai.agents.common import market_snapshot_from_state, trigger_from_state
from agentic_ai.state import WorkflowState

TREND_UP_THRESHOLD = float(os.environ.get("SIGNAL_TREND_UP_PCT", "0.5"))
TREND_DOWN_THRESHOLD = float(os.environ.get("SIGNAL_TREND_DOWN_PCT", "-0.5"))


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_trend(pct_change_5m: float | None) -> str:
    if pct_change_5m is None:
        return "sideways"
    if pct_change_5m >= TREND_UP_THRESHOLD:
        return "up"
    if pct_change_5m <= TREND_DOWN_THRESHOLD:
        return "down"
    return "sideways"


def compute_momentum_score(
    *,
    pct_change_5m: float | None,
    volume_ratio: float | None,
    triggered_value: float,
) -> float:
    """Heuristic 0.0–1.0 momentum from price change and volume."""
    price_component = 0.0
    if pct_change_5m is not None:
        price_component = min(1.0, abs(pct_change_5m) / 5.0)
    volume_component = 0.0
    if volume_ratio is not None:
        volume_component = min(1.0, max(0.0, volume_ratio - 1.0) / 4.0)
    trigger_component = min(1.0, abs(triggered_value) / 10.0)
    return round(
        min(1.0, 0.5 * price_component + 0.35 * volume_component + 0.15 * trigger_component),
        4,
    )


def compute_support_proximity(
    *,
    price: float | None,
    pct_change_1m: float | None,
    volatility_score: float | None,
) -> str | None:
    """
    Placeholder proximity label from enriched metrics (no external levels).
    """
    if price is None:
        return None
    if volatility_score is not None and volatility_score >= 0.5:
        return "high_volatility_band"
    if pct_change_1m is not None and abs(pct_change_1m) < 0.2:
        return "near_short_term_mean"
    return "neutral"


def build_signal_summary(state: WorkflowState) -> dict:
    trigger = trigger_from_state(state)
    snapshot = market_snapshot_from_state(state)

    pct_change_5m = _optional_float(snapshot.get("pct_change_5m"))
    pct_change_1m = _optional_float(snapshot.get("pct_change_1m"))
    volume_ratio = _optional_float(snapshot.get("volume_ratio"))
    volatility_score = _optional_float(snapshot.get("volatility_score"))
    price = _optional_float(snapshot.get("price"))

    return {
        "symbol": trigger.symbol,
        "rule_name": trigger.rule_name,
        "trend": compute_trend(pct_change_5m),
        "momentum_score": compute_momentum_score(
            pct_change_5m=pct_change_5m,
            volume_ratio=volume_ratio,
            triggered_value=trigger.triggered_value,
        ),
        "support_proximity": compute_support_proximity(
            price=price,
            pct_change_1m=pct_change_1m,
            volatility_score=volatility_score,
        ),
        "inputs": {
            "pct_change_5m": pct_change_5m,
            "pct_change_1m": pct_change_1m,
            "volume_ratio": volume_ratio,
            "volatility_score": volatility_score,
        },
    }


def signal_agent_node(state: WorkflowState) -> WorkflowState:
    return {"signal_summary": build_signal_summary(state)}
