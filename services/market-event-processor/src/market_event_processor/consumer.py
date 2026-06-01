"""Pub/Sub consumer for raw-market-events."""

from __future__ import annotations

import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import TYPE_CHECKING

import redis
from google.cloud import pubsub_v1

from market_event_processor.models import parse_raw_pubsub_message

if TYPE_CHECKING:
    from market_event_processor.enriched_publisher import EnrichedEventPublisher
    from market_event_processor.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class MarketEventConsumer:
    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        calculator: MetricsCalculator,
        publisher: EnrichedEventPublisher,
        *,
        subscriber: pubsub_v1.SubscriberClient | None = None,
    ) -> None:
        self._subscriber = subscriber or pubsub_v1.SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(
            project_id, subscription_id
        )
        self._calculator = calculator
        self._publisher = publisher
        self._running = False
        self._messages_processed = 0
        self._messages_published = 0

    @property
    def messages_processed(self) -> int:
        return self._messages_processed

    @property
    def messages_published(self) -> int:
        return self._messages_published

    @property
    def healthy(self) -> bool:
        return self._running

    def _handle_message(self, message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            upstream_id, raw, _envelope = parse_raw_pubsub_message(message.data)
        except ValueError as exc:
            logger.warning("Malformed raw event (acked): %s", exc)
            message.ack()
            return

        try:
            enriched = self._calculator.enrich(raw)
        except redis.RedisError as exc:
            logger.error(
                "Redis error enriching %s (nack): %s", raw.symbol, exc, exc_info=True
            )
            message.nack()
            return
        except Exception as exc:
            logger.error(
                "Enrichment error for %s (nack): %s",
                raw.symbol,
                exc,
                exc_info=True,
            )
            message.nack()
            return

        try:
            self._publisher.publish(enriched, upstream_message_id=upstream_id)
        except Exception as exc:
            logger.error(
                "Publish failed for %s (nack): %s", raw.symbol, exc, exc_info=True
            )
            message.nack()
            return

        self._messages_processed += 1
        self._messages_published += 1
        message.ack()
        logger.debug(
            "Enriched %s pct_5m=%s vol_ratio=%s",
            raw.symbol,
            enriched.pct_change_5m,
            enriched.volume_ratio,
        )

    def run(self) -> None:
        self._running = True
        flow_control = pubsub_v1.types.FlowControl(max_messages=100)
        streaming_pull_future = self._subscriber.subscribe(
            self._subscription_path,
            callback=self._handle_message,
            flow_control=flow_control,
        )
        logger.info("Market event processor consuming %s", self._subscription_path)
        try:
            streaming_pull_future.result()
        except FuturesTimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result(timeout=5)
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
            streaming_pull_future.result(timeout=5)
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False
