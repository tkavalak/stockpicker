from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from agentic_ai.agents.control_agent import apply_governance
from agentic_ai.governance.thresholds import GovernanceThresholds
from agentic_ai.models import ACTION_ALERT, ACTION_ESCALATE, ACTION_IGNORE, TriggerEvent


def _trigger() -> TriggerEvent:
    return TriggerEvent(
        event_id="evt-c1",
        symbol="AAPL",
        rule_name="PRICE_SPIKE_5M",
        triggered_value=2.5,
        threshold_value=2.0,
        enriched_event={},
        fired_at="2026-01-01T00:00:00+00:00",
    )


def _thresholds() -> GovernanceThresholds:
    return GovernanceThresholds(0.70, 0.90, 10.0)


def test_low_confidence_suppressed():
    cooldown = MagicMock()
    cooldown.is_in_cooldown.return_value = False
    decision = apply_governance(
        trigger=_trigger(),
        raw={"confidence": 0.5, "reason": "weak", "action_candidate": "ALERT"},
        context_summary={"available": False, "headlines": []},
        thresholds=_thresholds(),
        cooldown_store=cooldown,
    )
    assert decision.action == ACTION_IGNORE
    cooldown.record_alert.assert_not_called()


def test_cooldown_suppressed():
    cooldown = MagicMock()
    cooldown.is_in_cooldown.return_value = True
    decision = apply_governance(
        trigger=_trigger(),
        raw={"confidence": 0.85, "reason": "strong", "action_candidate": "ALERT"},
        context_summary=None,
        thresholds=_thresholds(),
        cooldown_store=cooldown,
    )
    assert decision.action == ACTION_IGNORE
    assert "cooldown" in decision.reason.lower()
    cooldown.record_alert.assert_not_called()


def test_escalation_upgrade():
    cooldown = MagicMock()
    cooldown.is_in_cooldown.return_value = False
    decision = apply_governance(
        trigger=_trigger(),
        raw={"confidence": 0.95, "reason": "major move", "action_candidate": "ALERT"},
        context_summary={"available": True, "summary": "Big news"},
        thresholds=_thresholds(),
        cooldown_store=cooldown,
    )
    assert decision.action == ACTION_ESCALATE
    cooldown.record_alert.assert_called_once()


def test_alert_approved_records_cooldown():
    cooldown = MagicMock()
    cooldown.is_in_cooldown.return_value = False
    decision = apply_governance(
        trigger=_trigger(),
        raw={"confidence": 0.80, "reason": "valid spike", "action_candidate": "ALERT"},
        context_summary=None,
        thresholds=_thresholds(),
        cooldown_store=cooldown,
    )
    assert decision.action == ACTION_ALERT
    cooldown.record_alert.assert_called_once_with(
        "AAPL", "PRICE_SPIKE_5M", window_minutes=10.0
    )


def test_cooldown_expired_allows_alert():
    store = MagicMock()
    store.is_in_cooldown.return_value = False
    decision = apply_governance(
        trigger=_trigger(),
        raw={"confidence": 0.75, "reason": "ok", "action_candidate": "ALERT"},
        context_summary=None,
        thresholds=_thresholds(),
        cooldown_store=store,
    )
    assert decision.action == ACTION_ALERT
