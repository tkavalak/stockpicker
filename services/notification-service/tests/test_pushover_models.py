from notification_service.models import (
    ACTION_ESCALATE,
    AlertDecision,
    pushover_message_body,
    pushover_title,
)


def test_pushover_title_escalate():
    decision = AlertDecision(
        decision_id="1",
        symbol="NVDA",
        action=ACTION_ESCALATE,
        signal_type="SPIKE",
        measured_magnitude=2.0,
        confidence_score=0.9,
        reason="Big move",
        event_timestamp="t",
    )
    assert pushover_title(decision).startswith("[ESCALATE]")
    assert "NVDA" in pushover_title(decision)


def test_pushover_message_body():
    decision = AlertDecision(
        decision_id="1",
        symbol="AAPL",
        action="ALERT",
        signal_type="PRICE_SPIKE_5M",
        measured_magnitude=2.5,
        confidence_score=0.85,
        reason="5m spike",
        event_timestamp="2026-01-01T00:00:00Z",
    )
    body = pushover_message_body(decision)
    assert "PRICE_SPIKE_5M" in body
    assert "85%" in body
