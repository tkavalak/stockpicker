"""Publish AlertDecision messages to alert-decisions."""

from __future__ import annotations

import logging
import time

from google.api_core import exceptions as gcp_exceptions
from google.cloud import pubsub_v1

from agentic_ai.models import (
    ACTION_ALERT,
    ACTION_ESCALATE,
    AlertDecision,
    build_alert_envelope,
    envelope_to_json_bytes,
)

logger = logging.getLogger(__name__)

TRANSIENT_EXCEPTIONS = (
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.DeadlineExceeded,
    gcp_exceptions.InternalServerError,
    gcp_exceptions.TooManyRequests,
    gcp_exceptions.Aborted,
)


class AlertDecisionPublisher:
    def __init__(
        self,
        project_id: str,
        topic_id: str,
        *,
        publisher: pubsub_v1.PublisherClient | None = None,
        max_retries: int = 3,
    ) -> None:
        self._publisher = publisher or pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_id)
        self._topic_id = topic_id
        self._max_retries = max_retries
        self._published_count = 0

    @property
    def published_count(self) -> int:
        return self._published_count

    @staticmethod
    def should_publish(decision: AlertDecision) -> bool:
        """Only ALERT and ESCALATE are published; IGNORE stays in logs only."""
        return decision.action in (ACTION_ALERT, ACTION_ESCALATE)

    def publish(self, decision: AlertDecision) -> str:
        if not self.should_publish(decision):
            raise ValueError(f"refusing to publish decision with action={decision.action}")
        envelope = build_alert_envelope(decision, topic=self._topic_id)
        data = envelope_to_json_bytes(envelope)

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                future = self._publisher.publish(
                    self._topic_path,
                    data,
                    message_id=envelope["message_id"],
                )
                message_id = future.result(timeout=30)
                self._published_count += 1
                logger.info(
                    "Published alert-decisions event_id=%s action=%s",
                    decision.event_id,
                    decision.action,
                )
                return message_id
            except TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                time.sleep(0.5 * (2 ** (attempt - 1)))

        assert last_exc is not None
        raise last_exc
