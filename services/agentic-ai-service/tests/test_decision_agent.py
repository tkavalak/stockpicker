from unittest.mock import MagicMock

from agentic_ai.agents.decision_agent import run_decision_agent
from agentic_ai.llm.router import LLMRouter, set_llm_router
from agentic_ai.models import ACTION_ALERT, TriggerEvent


def _base_state() -> dict:
    return {
        "trigger": TriggerEvent(
            event_id="evt-d1",
            symbol="NVDA",
            rule_name="VOLUME_SPIKE",
            triggered_value=4.0,
            threshold_value=3.0,
            enriched_event={"payload": {"volume_ratio": 4.0}},
            fired_at="2099-01-01T00:00:00+00:00",
        ).to_dict(),
        "market_snapshot": {"volume_ratio": 4.0, "pct_change_5m": 1.0},
        "signal_summary": {"trend": "up", "momentum_score": 0.6},
        "context_summary": {"available": False, "headlines": []},
    }


def test_decision_agent_parses_llm_response():
    vertex = MagicMock()
    vertex.available = True
    vertex.complete_with_retry.return_value = (
        '{"confidence": 0.82, "reason": "Volume spike with upward trend.", '
        '"action_candidate": "ALERT"}'
    )
    openai = MagicMock()
    openai.available = False
    set_llm_router(LLMRouter(vertex=vertex, openai=openai))
    try:
        raw = run_decision_agent(_base_state())
        assert raw["action_candidate"] == ACTION_ALERT
        assert raw["confidence"] == 0.82
        assert "Volume" in raw["reason"]
        assert raw["llm_provider"] == "vertex_ai"
    finally:
        set_llm_router(None)


def test_decision_agent_parse_failure_defaults_ignore():
    vertex = MagicMock()
    vertex.available = True
    vertex.complete_with_retry.return_value = "not json"
    openai = MagicMock()
    openai.available = False
    set_llm_router(LLMRouter(vertex=vertex, openai=openai))
    try:
        raw = run_decision_agent(_base_state())
        assert raw["action_candidate"] == "IGNORE"
        assert "parsing failed" in raw["reason"]
    finally:
        set_llm_router(None)


def test_decision_agent_llm_unavailable():
    vertex = MagicMock()
    vertex.available = False
    openai = MagicMock()
    openai.available = False
    set_llm_router(LLMRouter(vertex=vertex, openai=openai))
    try:
        raw = run_decision_agent(_base_state())
        assert raw["action_candidate"] == "IGNORE"
        assert "unavailable" in raw["reason"].lower()
    finally:
        set_llm_router(None)


def test_decision_agent_test_mode_bypasses_llm(monkeypatch):
    monkeypatch.setenv("AGENTIC_TEST_MODE", "1")
    raw = run_decision_agent(_base_state())
    assert raw["action_candidate"] == ACTION_ALERT
    assert raw["confidence"] == 0.85
    assert raw["llm_provider"] == "test_mode"
