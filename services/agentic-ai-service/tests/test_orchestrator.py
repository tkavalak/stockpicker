from unittest.mock import MagicMock

from agentic_ai.models import (
    ACTION_IGNORE,
    OUTCOME_DUPLICATE,
    OUTCOME_TIMEOUT,
    TriggerEvent,
    ignore_decision,
)
from agentic_ai.orchestrator import AgentOrchestrator


def _trigger() -> TriggerEvent:
    return TriggerEvent(
        event_id="evt-orch-1",
        symbol="TSLA",
        rule_name="PRICE_SPIKE_5M",
        triggered_value=2.1,
        threshold_value=2.0,
        enriched_event={"payload": {"symbol": "TSLA"}},
        fired_at="2099-01-01T00:00:00+00:00",
    )


def test_duplicate_skips_graph():
    prior = ignore_decision(_trigger(), reason="cached")
    store = MagicMock()
    store.get_prior_decision.return_value = prior
    orch = AgentOrchestrator(state_store=store)
    result = orch.run(_trigger())
    assert result.outcome == OUTCOME_DUPLICATE
    assert result.decision == prior
    store.save_decision.assert_not_called()


def test_should_publish_only_alert_escalate():
    orch = AgentOrchestrator(state_store=MagicMock())
    assert orch.should_publish(ignore_decision(_trigger(), reason="x")) is False
    from agentic_ai.models import AlertDecision

    alert = AlertDecision(
        event_id="e",
        symbol="AAPL",
        signal="R",
        confidence=0.9,
        reason="ok",
        action="ALERT",
        context_summary="",
        decided_at="t",
    )
    assert orch.should_publish(alert) is True


def test_timeout_returns_none_decision(monkeypatch):
    store = MagicMock()
    store.get_prior_decision.return_value = None
    orch = AgentOrchestrator(state_store=store, workflow_timeout_sec=0.001)

    def slow_invoke(_initial):
        import time

        time.sleep(0.05)
        return {"final_decision": ignore_decision(_trigger(), reason="late").to_dict()}

    monkeypatch.setattr(orch, "_invoke_graph", slow_invoke)
    result = orch.run(_trigger())
    assert result.outcome == OUTCOME_TIMEOUT
    assert result.decision is None
    store.save_decision.assert_called_once()
