"""Pub/Sub consumer for alert-decisions."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from google.cloud import pubsub_v1

from notification_service.models import parse_alert_decision_message

if TYPE_CHECKING:
    from notification_service.dispatcher import NotificationDispatcher

logger = logging.getLogger(__name__)


class NotificationConsumer:
    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        dispatcher: NotificationDispatcher,
        loop: asyncio.AbstractEventLoop,
        *,
        subscriber: pubsub_v1.SubscriberClient | None = None,
    ) -> None:
        self._subscriber = subscriber or pubsub_v1.SubscriberClient()
        self._subscription_path = self._subscriber.subscription_path(
            project_id, subscription_id
        )
        self._dispatcher = dispatcher
        self._loop = loop
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
        try:
            decision = parse_alert_decision_message(message.data)
        except ValueError as exc:
            logger.warning("Malformed alert decision (acked): %s", exc)
            message.ack()
            return

        try:
            await self._dispatcher.dispatch(decision)
            self._messages_processed += 1
            message.ack()
        except Exception as exc:
            logger.error(
                "Dispatch failed for decision %s: %s",
                decision.decision_id,
                exc,
                exc_info=True,
            )
            message.nack()

    def run(self) -> None:
        flow_control = pubsub_v1.types.FlowControl(max_messages=50)
        streaming_pull_future = self._subscriber.subscribe(
            self._subscription_path,
            callback=self._callback,
            flow_control=flow_control,
        )
        logger.info("Notification consumer listening on %s", self._subscription_path)
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
