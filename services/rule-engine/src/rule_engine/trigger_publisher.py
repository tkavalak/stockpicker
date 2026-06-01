"""Publish TriggerEvent messages to trigger-events."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from google.api_core import exceptions as gcp_exceptions
from google.cloud import pubsub_v1

from rule_engine.models import (
    EnrichedMarketEvent,
    RuleFire,
    TriggerEvent,
    build_trigger_envelope,
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


class TriggerEventPublisher:
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

    def publish_fire(
        self,
        *,
        upstream_message_id: str,
        event: EnrichedMarketEvent,
        fire: RuleFire,
        envelope_snapshot: dict,
    ) -> str:
        trigger = TriggerEvent(
            event_id=upstream_message_id,
            symbol=event.symbol,
            rule_name=fire.rule_name,
            triggered_value=fire.triggered_value,
            threshold_value=fire.threshold_value,
            enriched_event=envelope_snapshot,
            fired_at=datetime.now(timezone.utc).isoformat(),
        )
        envelope = build_trigger_envelope(trigger, topic=self._topic_id)
        data = envelope_to_json_bytes(envelope)

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                future = self._publisher.publish(
                    self._topic_path,
                    data,
                    message_id=envelope["message_id"],
                )
                return future.result(timeout=30)
            except TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                time.sleep(0.5 * (2 ** (attempt - 1)))

        assert last_exc is not None
        raise last_exc
