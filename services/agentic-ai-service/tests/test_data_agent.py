from datetime import datetime, timedelta, timezone

from agentic_ai.agents.data_agent import data_agent_node
from agentic_ai.models import ACTION_IGNORE, TriggerEvent


def _state(**kwargs) -> dict:
    base = {
        "trigger": TriggerEvent(
            event_id="evt-1",
            symbol="AAPL",
            rule_name="PRICE_SPIKE_5M",
            triggered_value=2.5,
            threshold_value=2.0,
            enriched_event={"payload": {"symbol": "AAPL", "price": 150.0}},
            fired_at=datetime.now(timezone.utc).isoformat(),
        ).to_dict()
    }
    base.update(kwargs)
    return base


def test_valid_trigger_builds_snapshot():
    out = data_agent_node(_state())
    assert out.get("abort") is False
    assert out["market_snapshot"]["symbol"] == "AAPL"
    assert out["market_snapshot"]["rule_name"] == "PRICE_SPIKE_5M"


def test_invalid_rule_aborts():
    state = _state()
    state["trigger"]["rule_name"] = "UNKNOWN_RULE"
    out = data_agent_node(state)
    assert out["abort"] is True
    assert out["final_decision"]["action"] == ACTION_IGNORE


def test_missing_symbol_aborts():
    state = _state()
    state["trigger"]["symbol"] = ""
    out = data_agent_node(state)
    assert out["abort"] is True


def test_stale_trigger_aborts():
    stale = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    state = _state()
    state["trigger"]["fired_at"] = stale
    out = data_agent_node(state)
    assert out["abort"] is True
    assert "stale" in out["final_decision"]["reason"]
