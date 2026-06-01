from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from agentic_ai.agents.data_agent import data_agent_node
from agentic_ai.graph import get_compiled_graph
from agentic_ai.llm.router import LLMRouter, set_llm_router
from agentic_ai.agents.control_agent import set_governance_thresholds
from agentic_ai.governance.cooldown import CooldownStore, set_cooldown_store
from agentic_ai.governance.thresholds import GovernanceThresholds
from agentic_ai.models import ACTION_ESCALATE, ACTION_IGNORE, TriggerEvent


def _fresh_trigger() -> dict:
    fired = datetime.now(timezone.utc).isoformat()
    return TriggerEvent(
        event_id="evt-graph-1",
        symbol="AAPL",
        rule_name="VOLUME_SPIKE",
        triggered_value=3.5,
        threshold_value=3.0,
        enriched_event={
            "payload": {
                "symbol": "AAPL",
                "volume_ratio": 3.5,
                "pct_change_5m": 2.0,
                "price": 100.0,
            }
        },
        fired_at=fired,
    ).to_dict()


def test_graph_runs_to_ignore_stub():
    vertex = MagicMock()
    vertex.available = True
    vertex.complete_with_retry.return_value = (
        '{"confidence": 0.0, "reason": "Stub test ignore.", "action_candidate": "IGNORE"}'
    )
    openai = MagicMock()
    openai.available = False
    set_llm_router(LLMRouter(vertex=vertex, openai=openai))
    try:
        graph = get_compiled_graph()
        result = graph.invoke({"trigger": _fresh_trigger(), "abort": False})
        final = result.get("final_decision")
        assert isinstance(final, dict)
        assert final.get("action") == ACTION_IGNORE
        raw = result.get("raw_decision")
        assert raw.get("reason") == "Stub test ignore."
    finally:
        set_llm_router(None)


def test_graph_escalates_high_confidence():
    vertex = MagicMock()
    vertex.available = True
    vertex.complete_with_retry.return_value = (
        '{"confidence": 0.95, "reason": "Strong volume and trend.", "action_candidate": "ALERT"}'
    )
    openai = MagicMock()
    openai.available = False
    cooldown = MagicMock(spec=CooldownStore)
    cooldown.is_in_cooldown.return_value = False
    set_llm_router(LLMRouter(vertex=vertex, openai=openai))
    set_governance_thresholds(GovernanceThresholds(0.70, 0.90, 10.0))
    set_cooldown_store(cooldown)
    try:
        result = get_compiled_graph().invoke(
            {"trigger": _fresh_trigger(), "abort": False}
        )
        assert result["final_decision"]["action"] == ACTION_ESCALATE
        cooldown.record_alert.assert_called_once()
    finally:
        set_llm_router(None)
        set_cooldown_store(None)
        set_governance_thresholds(None)


def test_data_agent_aborts_stale_trigger():
    stale = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    state = {
        "trigger": TriggerEvent(
            event_id="evt-stale",
            symbol="AAPL",
            rule_name="PRICE_SPIKE_5M",
            triggered_value=1.0,
            threshold_value=2.0,
            enriched_event={},
            fired_at=stale,
        ).to_dict()
    }
    out = data_agent_node(state)
    assert out.get("abort") is True
    assert out["final_decision"]["action"] == ACTION_IGNORE
