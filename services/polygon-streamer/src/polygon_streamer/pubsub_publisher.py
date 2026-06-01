"""Publish MarketEventMessage envelopes to GCP Pub/Sub."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from google.api_core import exceptions as gcp_exceptions
from google.cloud import pubsub_v1

from polygon_streamer.models import (
    MarketEventMessage,
    build_pubsub_envelope,
    envelope_to_json_bytes,
)

if TYPE_CHECKING:
    from google.cloud.pubsub_v1 import PublisherClient

logger = logging.getLogger(__name__)

TRANSIENT_EXCEPTIONS = (
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.DeadlineExceeded,
    gcp_exceptions.InternalServerError,
    gcp_exceptions.TooManyRequests,
    gcp_exceptions.Aborted,
)


class PubSubPublisher:
    def __init__(
        self,
        project_id: str,
        topic_id: str,
        *,
        publisher: PublisherClient | None = None,
        max_retries: int = 3,
        base_retry_delay_sec: float = 0.5,
    ) -> None:
        self._publisher = publisher or pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_id)
        self._topic_id = topic_id
        self._max_retries = max_retries
        self._base_retry_delay_sec = base_retry_delay_sec

    @property
    def topic_path(self) -> str:
        return self._topic_path

    def publish(self, event: MarketEventMessage) -> str:
        envelope = build_pubsub_envelope(event, topic=self._topic_id)
        data = envelope_to_json_bytes(envelope)
        message_id = envelope["message_id"]

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                future = self._publisher.publish(
                    self._topic_path,
                    data,
                    message_id=message_id,
                )
                return future.result(timeout=30)
            except TRANSIENT_EXCEPTIONS as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                delay = self._base_retry_delay_sec * (2 ** (attempt - 1))
                logger.warning(
                    "Pub/Sub publish retry %d/%d in %.1fs: %s",
                    attempt,
                    self._max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)

        assert last_exc is not None
        raise last_exc
