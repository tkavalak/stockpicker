"""Pub/Sub consumer for enriched-market-events."""

from __future__ import annotations

import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1

from rule_engine.models import parse_enriched_pubsub_message
from rule_engine.rules import evaluate_rules

if TYPE_CHECKING:
    from rule_engine.rule_config_loader import RuleConfigLoader
    from rule_engine.trigger_publisher import TriggerEventPublisher

logger = logging.getLogger(__name__)


class RuleEngineConsumer:
    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        config_loader: RuleConfigLoader,
        trigger_publisher: TriggerEventPublisher,
        *,
        subscriber: pubsub_v1.SubscriberClient | None = None,
    ) -> None:
        self._subscriber = subscriber or pubsub_v1.SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(
            project_id, subscription_id
        )
        self._config_loader = config_loader
        self._trigger_publisher = trigger_publisher
        self._running = False
        self._messages_processed = 0
        self._triggers_published = 0

    @property
    def messages_processed(self) -> int:
        return self._messages_processed

    @property
    def triggers_published(self) -> int:
        return self._triggers_published

    def _handle_message(self, message: pubsub_v1.subscriber.message.Message) -> None:
        try:
            upstream_id, event, envelope = parse_enriched_pubsub_message(message.data)
        except ValueError as exc:
            logger.warning("Malformed enriched event (acked): %s", exc)
            message.ack()
            return

        configs = self._config_loader.get_configs()
        try:
            fires = evaluate_rules(event, configs)
        except Exception as exc:
            logger.error(
                "Rule evaluation error for %s (acked): %s",
                event.symbol,
                exc,
                exc_info=True,
            )
            message.ack()
            return

        for fire in fires:
            try:
                self._trigger_publisher.publish_fire(
                    upstream_message_id=upstream_id,
                    event=event,
                    fire=fire,
                    envelope_snapshot=envelope,
                )
                self._triggers_published += 1
                logger.info(
                    "Trigger published symbol=%s rule=%s value=%.4f threshold=%.4f",
                    event.symbol,
                    fire.rule_name,
                    fire.triggered_value,
                    fire.threshold_value,
                )
            except Exception as exc:
                logger.error(
                    "Failed to publish trigger symbol=%s rule=%s: %s",
                    event.symbol,
                    fire.rule_name,
                    exc,
                )

        self._messages_processed += 1
        message.ack()

    def run(self) -> None:
        self._running = True
        flow_control = pubsub_v1.types.FlowControl(max_messages=100)
        streaming_pull_future = self._subscriber.subscribe(
            self._subscription_path,
            callback=self._handle_message,
            flow_control=flow_control,
        )
        logger.info("Rule engine consuming %s", self._subscription_path)
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
