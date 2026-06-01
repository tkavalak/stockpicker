"""Firestore idempotency for agent workflows (agent_state collection)."""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import firestore

from agentic_ai.models import AlertDecision, alert_decision_from_state

logger = logging.getLogger(__name__)


class AgentStateStore:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        collection: str = "agent_state",
        client: firestore.Client | None = None,
    ) -> None:
        self._client = client or firestore.Client(project=project_id)
        self._collection = collection

    def _doc_ref(self, event_id: str) -> firestore.DocumentReference:
        return self._client.collection(self._collection).document(event_id)

    def get_prior_decision(self, event_id: str) -> AlertDecision | None:
        doc = self._doc_ref(event_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        decision_blob = data.get("decision")
        if not isinstance(decision_blob, dict):
            return None
        trigger_blob = data.get("trigger") or {}
        from agentic_ai.models import TriggerEvent

        trigger = TriggerEvent.from_dict(trigger_blob) if trigger_blob else TriggerEvent(
            event_id=event_id,
            symbol=str(decision_blob.get("symbol", "")),
            rule_name=str(decision_blob.get("signal", "")),
            triggered_value=float(decision_blob.get("measured_magnitude", 0)),
            threshold_value=0.0,
            enriched_event={},
            fired_at=str(decision_blob.get("decided_at", "")),
        )
        return alert_decision_from_state(decision_blob, trigger)

    def save_decision(
        self,
        *,
        event_id: str,
        trigger: dict[str, Any],
        decision: AlertDecision,
        outcome: str,
        latency_ms: int,
    ) -> None:
        self._doc_ref(event_id).set(
            {
                "event_id": event_id,
                "trigger": trigger,
                "decision": decision.to_dict(),
                "outcome": outcome,
                "latency_ms": latency_ms,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.debug("Persisted agent_state/%s outcome=%s", event_id, outcome)
