"""Async Pub/Sub consumer for trigger-events with concurrency limits."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1

from agentic_ai.models import (
    ACTION_IGNORE,
    OUTCOME_TIMEOUT,
    parse_trigger_pubsub_message,
)

if TYPE_CHECKING:
    from agentic_ai.orchestrator import AgentOrchestrator
    from agentic_ai.publisher import AlertDecisionPublisher

logger = logging.getLogger(__name__)

MAX_CONCURRENT_WORKFLOWS = int(os.environ.get("MAX_CONCURRENT_WORKFLOWS", "5"))


class TriggerEventConsumer:
    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        orchestrator: AgentOrchestrator,
        publisher: AlertDecisionPublisher,
        loop: asyncio.AbstractEventLoop,
        *,
        subscriber: pubsub_v1.SubscriberClient | None = None,
        max_concurrent: int = MAX_CONCURRENT_WORKFLOWS,
    ) -> None:
        self._subscriber = subscriber or pubsub_v1.SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(
            project_id, subscription_id
        )
        self._orchestrator = orchestrator
        self._publisher = publisher
        self._loop = loop
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._messages_processed = 0
        self._healthy = True

    @property
    def messages_processed(self) -> int:
        return self._messages_processed

    @property
    def healthy(self) -> bool:
        return self._healthy

    def _callback(self, message: pubsub_v1.subscriber.message.Message) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self._handle_message(message), self._loop
        )
        try:
            future.result(timeout=120)
        except Exception as exc:
            logger.error("Unhandled consumer error: %s", exc, exc_info=True)
            message.nack()

    async def _handle_message(self, message: pubsub_v1.subscriber.message.Message) -> None:
        async with self._semaphore:
            try:
                trigger = parse_trigger_pubsub_message(message.data)
            except ValueError as exc:
                logger.warning("Malformed trigger (acked): %s", exc)
                message.ack()
                return

            try:
                result = await asyncio.to_thread(self._orchestrator.run, trigger)
            except Exception as exc:
                logger.error(
                    "Workflow failed event_id=%s: %s",
                    trigger.event_id,
                    exc,
                    exc_info=True,
                )
                message.nack()
                return

            if result.outcome == OUTCOME_TIMEOUT:
                logger.info(
                    "Workflow TIMEOUT dropped event_id=%s latency_ms=%d",
                    trigger.event_id,
                    result.latency_ms,
                )
                message.ack()
                self._messages_processed += 1
                return

            decision = result.decision
            if decision and self._orchestrator.should_publish(decision):
                try:
                    await asyncio.to_thread(self._publisher.publish, decision)
                except Exception as exc:
                    logger.error(
                        "Publish failed event_id=%s: %s",
                        trigger.event_id,
                        exc,
                        exc_info=True,
                    )
                    message.nack()
                    return
            elif decision and decision.action == ACTION_IGNORE:
                logger.info(
                    "IGNORE decision event_id=%s reason=%s (not published)",
                    decision.event_id,
                    decision.reason,
                )

            self._messages_processed += 1
            message.ack()

    def run(self) -> None:
        flow_control = pubsub_v1.types.FlowControl(
            max_messages=MAX_CONCURRENT_WORKFLOWS * 2
        )
        streaming_pull_future = self._subscriber.subscribe(
            self._subscription_path,
            callback=self._callback,
            flow_control=flow_control,
        )
        logger.info(
            "Agentic AI consuming %s (max_concurrent=%d)",
            self._subscription_path,
            MAX_CONCURRENT_WORKFLOWS,
        )
        try:
            streaming_pull_future.result()
        except Exception as exc:
            self._healthy = False
            logger.error("Subscriber stopped: %s", exc)
            raise
        finally:
            streaming_pull_future.cancel()

    def stop(self) -> None:
        self._healthy = False
