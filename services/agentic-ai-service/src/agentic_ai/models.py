"""TriggerEvent, AlertDecision, and Pub/Sub envelope helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

SOURCE_CONTAINER = "agentic-ai-service"
SCHEMA_VERSION = "1.0"

ACTION_ALERT = "ALERT"
ACTION_ESCALATE = "ESCALATE"
ACTION_IGNORE = "IGNORE"

OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_DUPLICATE = "DUPLICATE"
OUTCOME_IGNORE = "IGNORE"


@dataclass(frozen=True)
class TriggerEvent:
    event_id: str
    symbol: str
    rule_name: str
    triggered_value: float
    threshold_value: float
    enriched_event: dict[str, Any]
    fired_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TriggerEvent:
        enriched = data.get("enriched_event")
        if not isinstance(enriched, dict):
            enriched = {}
        return cls(
            event_id=str(data.get("event_id") or ""),
            symbol=str(data["symbol"]).upper(),
            rule_name=str(data.get("rule_name") or ""),
            triggered_value=float(data.get("triggered_value") or 0),
            threshold_value=float(data.get("threshold_value") or 0),
            enriched_event=enriched,
            fired_at=str(data.get("fired_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlertDecision:
    event_id: str
    symbol: str
    signal: str
    confidence: float
    reason: str
    action: str
    context_summary: str
    decided_at: str
    measured_magnitude: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_notification_payload(self) -> dict[str, Any]:
        """Shape consumed by notification-service AlertDecision.from_dict."""
        return {
            "decision_id": self.event_id,
            "event_id": self.event_id,
            "symbol": self.symbol,
            "action": self.action,
            "signal_type": self.signal,
            "rule_name": self.signal,
            "measured_magnitude": self.measured_magnitude,
            "triggered_value": self.measured_magnitude,
            "confidence_score": self.confidence,
            "reason": self.reason,
            "event_timestamp": self.decided_at,
            "context_summary": self.context_summary,
        }


def parse_trigger_pubsub_message(data: bytes) -> TriggerEvent:
    try:
        envelope = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON envelope: {exc}") from exc

    if not isinstance(envelope, dict):
        raise ValueError("envelope must be a JSON object")

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("envelope missing payload object")

    trigger = TriggerEvent.from_dict(payload)
    if not trigger.event_id:
        trigger_id = str(envelope.get("message_id") or "")
        if not trigger_id:
            raise ValueError("trigger event_id required")
        trigger = TriggerEvent(
            event_id=trigger_id,
            symbol=trigger.symbol,
            rule_name=trigger.rule_name,
            triggered_value=trigger.triggered_value,
            threshold_value=trigger.threshold_value,
            enriched_event=trigger.enriched_event,
            fired_at=trigger.fired_at,
        )
    if not trigger.symbol or not trigger.rule_name:
        raise ValueError("trigger missing symbol or rule_name")
    return trigger


def build_alert_envelope(decision: AlertDecision, *, topic: str) -> dict[str, Any]:
    return {
        "message_id": str(uuid.uuid4()),
        "source_container": SOURCE_CONTAINER,
        "topic": topic,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "payload": decision.to_notification_payload(),
    }


def envelope_to_json_bytes(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def alert_decision_from_state(final: dict[str, Any], trigger: TriggerEvent) -> AlertDecision:
    return AlertDecision(
        event_id=str(final.get("event_id") or trigger.event_id),
        symbol=str(final.get("symbol") or trigger.symbol).upper(),
        signal=str(final.get("signal") or trigger.rule_name),
        confidence=float(final.get("confidence", 0.0)),
        reason=str(final.get("reason") or ""),
        action=str(final.get("action", ACTION_IGNORE)).upper(),
        context_summary=str(final.get("context_summary") or ""),
        decided_at=str(
            final.get("decided_at") or datetime.now(timezone.utc).isoformat()
        ),
        measured_magnitude=float(
            final.get("measured_magnitude", trigger.triggered_value)
        ),
    )


def ignore_decision(trigger: TriggerEvent, *, reason: str) -> AlertDecision:
    return AlertDecision(
        event_id=trigger.event_id,
        symbol=trigger.symbol,
        signal=trigger.rule_name,
        confidence=0.0,
        reason=reason,
        action=ACTION_IGNORE,
        context_summary="",
        decided_at=datetime.now(timezone.utc).isoformat(),
        measured_magnitude=trigger.triggered_value,
    )
