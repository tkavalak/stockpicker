from agentic_ai.agents.signal_agent import (
    build_signal_summary,
    compute_momentum_score,
    compute_trend,
)
from agentic_ai.models import TriggerEvent


def _state_with_snapshot(snapshot: dict) -> dict:
    return {
        "trigger": TriggerEvent(
            event_id="e1",
            symbol="NVDA",
            rule_name="VOLUME_SPIKE",
            triggered_value=4.0,
            threshold_value=3.0,
            enriched_event={},
            fired_at="2026-01-01T00:00:00+00:00",
        ).to_dict(),
        "market_snapshot": snapshot,
    }


def test_trend_up():
    assert compute_trend(1.2) == "up"
    assert compute_trend(-1.2) == "down"
    assert compute_trend(0.1) == "sideways"


def test_signal_summary_from_enriched_fields():
    summary = build_signal_summary(
        _state_with_snapshot(
            {
                "pct_change_5m": 2.0,
                "pct_change_1m": 0.1,
                "volume_ratio": 3.5,
                "volatility_score": 0.2,
                "price": 100.0,
            }
        )
    )
    assert summary["trend"] == "up"
    assert summary["momentum_score"] > 0
    assert summary["support_proximity"] == "near_short_term_mean"
    assert summary["symbol"] == "NVDA"


def test_momentum_score_bounded():
    score = compute_momentum_score(
        pct_change_5m=10.0, volume_ratio=20.0, triggered_value=50.0
    )
    assert 0.0 <= score <= 1.0
