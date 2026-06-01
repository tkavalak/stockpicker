from notification_service.models import (
    ACTION_ESCALATE,
    AlertDecision,
    teams_alert_card,
    twilio_message_body,
)


def test_teams_card_has_adaptive_schema():
    decision = AlertDecision(
        decision_id="1",
        symbol="AAPL",
        action=ACTION_ESCALATE,
        signal_type="SPIKE",
        measured_magnitude=1.0,
        confidence_score=0.95,
        reason="Big move",
        event_timestamp="t",
    )
    card = teams_alert_card(decision)
    assert card["attachments"][0]["contentType"].endswith("adaptive")
    assert "AAPL" in str(card)


def test_twilio_format():
    decision = AlertDecision(
        decision_id="1",
        symbol="TSLA",
        action="ALERT",
        signal_type="VOLUME",
        measured_magnitude=3.0,
        confidence_score=0.8,
        reason="Volume spike detected",
        event_timestamp="t",
    )
    text = twilio_message_body(decision)
    assert "[StockPicker]" in text
    assert "TSLA" in text
    assert "confidence" in text
