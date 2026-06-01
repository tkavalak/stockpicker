from agentic_ai.agents.signal_agent import build_signal_summary
from agentic_ai.llm.prompt import build_decision_prompt
from agentic_ai.models import TriggerEvent


def test_build_decision_prompt_includes_signals_and_news():
    state = {
        "trigger": TriggerEvent(
            event_id="e1",
            symbol="AAPL",
            rule_name="PRICE_SPIKE_5M",
            triggered_value=2.5,
            threshold_value=2.0,
            enriched_event={},
            fired_at="2026-01-01T00:00:00+00:00",
        ).to_dict(),
        "market_snapshot": {
            "pct_change_5m": 2.1,
            "volume_ratio": 3.0,
            "price": 150.0,
        },
        "signal_summary": build_signal_summary(
            {
                "trigger": TriggerEvent(
                    event_id="e1",
                    symbol="AAPL",
                    rule_name="PRICE_SPIKE_5M",
                    triggered_value=2.5,
                    threshold_value=2.0,
                    enriched_event={},
                    fired_at="2026-01-01T00:00:00+00:00",
                ).to_dict(),
                "market_snapshot": {
                    "pct_change_5m": 2.1,
                    "volume_ratio": 3.0,
                    "price": 150.0,
                },
            }
        ),
        "context_summary": {
            "available": True,
            "headlines": [{"title": "Apple beats estimates"}],
            "summary": "Apple beats estimates",
        },
    }
    system, user = build_decision_prompt(state)
    assert "JSON" in system
    assert "PRICE_SPIKE_5M" in user
    assert "pct_change_5m" in user
    assert "Apple beats estimates" in user


def test_prompt_notes_missing_context():
    state = {
        "trigger": TriggerEvent(
            event_id="e2",
            symbol="TSLA",
            rule_name="VOLUME_SPIKE",
            triggered_value=1.0,
            threshold_value=1.0,
            enriched_event={},
            fired_at="2026-01-01T00:00:00+00:00",
        ).to_dict(),
        "market_snapshot": {},
        "signal_summary": {},
        "context_summary": {"available": False, "headlines": []},
    }
    _, user = build_decision_prompt(state)
    assert '"context_available": false' in user
