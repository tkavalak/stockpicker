import json

from agentic_ai.models import (
    ACTION_IGNORE,
    TriggerEvent,
    build_alert_envelope,
    parse_trigger_pubsub_message,
)


def test_parse_trigger_envelope():
    trigger = TriggerEvent(
        event_id="evt-1",
        symbol="AAPL",
        rule_name="PRICE_SPIKE_5M",
        triggered_value=2.5,
        threshold_value=2.0,
        enriched_event={"payload": {"price": 100}},
        fired_at="2026-01-01T12:00:00+00:00",
    )
    envelope = {
        "message_id": "msg-1",
        "payload": trigger.to_dict(),
    }
    parsed = parse_trigger_pubsub_message(json.dumps(envelope).encode())
    assert parsed.event_id == "evt-1"
    assert parsed.symbol == "AAPL"


def test_build_alert_envelope():
    from agentic_ai.models import AlertDecision

    decision = AlertDecision(
        event_id="evt-1",
        symbol="AAPL",
        signal="PRICE_SPIKE_5M",
        confidence=0.8,
        reason="test",
        action=ACTION_IGNORE,
        context_summary="",
        decided_at="2026-01-01T12:00:00+00:00",
        measured_magnitude=2.5,
    )
    env = build_alert_envelope(decision, topic="alert-decisions")
    assert env["topic"] == "alert-decisions"
    assert env["payload"]["decision_id"] == "evt-1"
