import json

import pytest

from notification_service.models import (
    ACTION_ESCALATE,
    ACTION_IGNORE,
    AlertDecision,
    email_alert_payload,
    parse_alert_decision_message,
    slack_alert_payload,
)


def test_parse_alert_decision_envelope():
    envelope = {
        "message_id": "dec-1",
        "payload": {
            "symbol": "AAPL",
            "action": "ALERT",
            "signal_type": "PRICE_SPIKE_5M",
            "measured_magnitude": 2.5,
            "confidence_score": 0.9,
            "reason": "5m price spike",
            "event_timestamp": "2026-01-01T12:00:00Z",
        },
    }
    decision = parse_alert_decision_message(json.dumps(envelope).encode())
    assert decision.symbol == "AAPL"
    assert decision.decision_id == "dec-1"
    assert decision.measured_magnitude == 2.5


def test_escalate_email_subject():
    decision = AlertDecision(
        decision_id="1",
        symbol="TSLA",
        action=ACTION_ESCALATE,
        signal_type="VOLUME_SPIKE",
        measured_magnitude=4.0,
        confidence_score=0.8,
        reason="volume",
        event_timestamp="t",
    )
    email = email_alert_payload(decision)
    assert email["subject"].startswith("[ESCALATE]")


def test_slack_escalate_text():
    decision = AlertDecision(
        decision_id="1",
        symbol="TSLA",
        action=ACTION_ESCALATE,
        signal_type="VOLUME_SPIKE",
        measured_magnitude=4.0,
        confidence_score=0.8,
        reason="volume",
        event_timestamp="t",
    )
    payload = slack_alert_payload(decision)
    assert "ESCALATE" in payload["text"]


def test_ignore_action_parsed():
    decision = AlertDecision.from_dict({"symbol": "X", "action": ACTION_IGNORE})
    assert decision.action == ACTION_IGNORE


def test_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_alert_decision_message(b"not json")
