"""AlertDecision and delivery payload models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

ACTION_ALERT = "ALERT"
ACTION_ESCALATE = "ESCALATE"
ACTION_IGNORE = "IGNORE"


@dataclass(frozen=True)
class AlertDecision:
    decision_id: str
    symbol: str
    action: str
    signal_type: str
    measured_magnitude: float
    confidence_score: float
    reason: str
    event_timestamp: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertDecision:
        return cls(
            decision_id=str(data.get("decision_id") or data.get("event_id") or ""),
            symbol=str(data["symbol"]).upper(),
            action=str(data.get("action", ACTION_ALERT)).upper(),
            signal_type=str(data.get("signal_type") or data.get("rule_name") or "unknown"),
            measured_magnitude=float(
                data.get("measured_magnitude") or data.get("triggered_value") or 0
            ),
            confidence_score=float(data.get("confidence_score", 1.0)),
            reason=str(data.get("reason") or ""),
            event_timestamp=str(
                data.get("event_timestamp")
                or data.get("timestamp")
                or datetime.now(timezone.utc).isoformat()
            ),
        )


@dataclass(frozen=True)
class DeliveryResult:
    channel: str
    status: str
    http_status: int | None
    latency_ms: int
    error: str | None = None


@dataclass(frozen=True)
class NotificationAuditRecord:
    decision_id: str
    channel: str
    symbol: str
    status: str
    http_status: int | None
    latency_ms: int
    dispatched_at: str

    def to_bq_row(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "channel": self.channel,
            "symbol": self.symbol,
            "status": self.status,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "dispatched_at": self.dispatched_at,
        }


def parse_alert_decision_message(data: bytes) -> AlertDecision:
    try:
        envelope = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc

    if not isinstance(envelope, dict):
        raise ValueError("envelope must be object")

    payload = envelope.get("payload", envelope)
    if not isinstance(payload, dict):
        raise ValueError("missing payload object")

    decision = AlertDecision.from_dict(payload)
    if not decision.decision_id:
        decision_id = str(envelope.get("message_id") or "")
        if not decision_id:
            raise ValueError("decision_id required")
        return AlertDecision(
            decision_id=decision_id,
            symbol=decision.symbol,
            action=decision.action,
            signal_type=decision.signal_type,
            measured_magnitude=decision.measured_magnitude,
            confidence_score=decision.confidence_score,
            reason=decision.reason,
            event_timestamp=decision.event_timestamp,
        )
    return decision


def slack_alert_payload(decision: AlertDecision) -> dict[str, Any]:
    escalate = decision.action == ACTION_ESCALATE
    header = "ESCALATE" if escalate else "Stock Movement Alert"
    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{header}: {decision.symbol}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Symbol:*\n{decision.symbol}"},
                {"type": "mrkdwn", "text": f"*Signal:*\n{decision.signal_type}"},
                {"type": "mrkdwn", "text": f"*Magnitude:*\n{decision.measured_magnitude:.4f}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:*\n{decision.confidence_score:.0%}",
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Reason:*\n{decision.reason or '—'}"},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Event time: {decision.event_timestamp}",
                }
            ],
        },
    ]
    text = (
        f"{'[ESCALATE] ' if escalate else ''}{decision.symbol} "
        f"{decision.signal_type}: {decision.measured_magnitude:.4f}"
    )
    return {"text": text, "blocks": blocks}


def email_alert_payload(
    decision: AlertDecision,
    *,
    dashboard_url: str = "#",
) -> dict[str, str]:
    escalate = decision.action == ACTION_ESCALATE
    prefix = "[ESCALATE] " if escalate else ""
    subject = (
        f"{prefix}[StockPicker] {decision.symbol} {decision.signal_type} alert"
    )
    html = f"""
    <html><body>
      <h2>{prefix}Movement Alert: {decision.symbol}</h2>
      <table>
        <tr><td><b>Symbol</b></td><td>{decision.symbol}</td></tr>
        <tr><td><b>Movement type</b></td><td>{decision.signal_type}</td></tr>
        <tr><td><b>Measured magnitude</b></td><td>{decision.measured_magnitude:.4f}</td></tr>
        <tr><td><b>Confidence</b></td><td>{decision.confidence_score:.0%}</td></tr>
        <tr><td><b>Reason</b></td><td>{decision.reason or '—'}</td></tr>
        <tr><td><b>Event timestamp</b></td><td>{decision.event_timestamp}</td></tr>
      </table>
      <p><a href="{dashboard_url}">View dashboard</a></p>
    </body></html>
    """
    return {"subject": subject, "html": html}


def teams_alert_card(decision: AlertDecision) -> dict[str, Any]:
    escalate = decision.action == ACTION_ESCALATE
    title = f"{'[ESCALATE] ' if escalate else ''}Stock Alert: {decision.symbol}"
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": title,
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Attention" if escalate else "Default",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Symbol", "value": decision.symbol},
                                {"title": "Signal", "value": decision.signal_type},
                                {
                                    "title": "Magnitude",
                                    "value": f"{decision.measured_magnitude:.4f}",
                                },
                                {
                                    "title": "Confidence",
                                    "value": f"{decision.confidence_score:.0%}",
                                },
                                {
                                    "title": "Time",
                                    "value": decision.event_timestamp,
                                },
                            ],
                        },
                        {
                            "type": "TextBlock",
                            "text": decision.reason or "—",
                            "wrap": True,
                        },
                    ],
                },
            }
        ],
    }


def pushover_title(decision: AlertDecision) -> str:
    prefix = "[ESCALATE] " if decision.action == ACTION_ESCALATE else ""
    return f"{prefix}StockPicker: {decision.symbol}"


def pushover_message_body(decision: AlertDecision) -> str:
    return (
        f"{decision.signal_type}\n"
        f"{decision.reason}\n"
        f"Magnitude: {decision.measured_magnitude:.4f}\n"
        f"Confidence: {decision.confidence_score:.0%}\n"
        f"Time: {decision.event_timestamp}"
    )


def twilio_message_body(decision: AlertDecision) -> str:
    prefix = "[ESCALATE] " if decision.action == ACTION_ESCALATE else ""
    return (
        f"{prefix}[StockPicker] {decision.symbol} {decision.signal_type}: "
        f"{decision.reason} (confidence: {decision.confidence_score:.0%})"
    )


def sample_test_decision() -> AlertDecision:
    return AlertDecision(
        decision_id="test-notification",
        symbol="TEST",
        action=ACTION_ALERT,
        signal_type="TEST_ALERT",
        measured_magnitude=1.0,
        confidence_score=1.0,
        reason="This is a StockPicker channel test message.",
        event_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def channel_failure_decision(channel_type: str, error: str) -> AlertDecision:
    return AlertDecision(
        decision_id=f"channel-error-{channel_type}",
        symbol="SYSTEM",
        action=ACTION_ALERT,
        signal_type="CHANNEL_FAILURE",
        measured_magnitude=0.0,
        confidence_score=1.0,
        reason=(
            f"Notification channel '{channel_type}' failed {3} consecutive deliveries. "
            f"Last error: {error}"
        ),
        event_timestamp=datetime.now(timezone.utc).isoformat(),
    )
