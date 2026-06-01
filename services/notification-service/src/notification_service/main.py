"""Notification Service entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading

from notification_service.admin import NotificationAdmin
from notification_service.audit_logger import AuditLogger
from notification_service.channel_dispatch import ChannelDispatcher
from notification_service.config_loader import NotificationConfigLoader
from notification_service.config_store import NotificationConfigStore
from notification_service.consumer import NotificationConsumer
from notification_service.dispatcher import NotificationDispatcher
from notification_service.router import NotificationRouter

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise ValueError(f"{name} must be set")
    return value


async def _run_admin(admin: NotificationAdmin) -> None:
    await admin.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await admin.stop()


def main() -> None:
    project_id = _env("GCP_PROJECT_ID")
    subscription_id = os.environ.get(
        "PUBSUB_SUBSCRIPTION_NOTIFICATION",
        "notification-alert-decisions",
    )
    dataset_id = os.environ.get("BIGQUERY_DATASET", "stock_picker")
    table_id = os.environ.get("BIGQUERY_TABLE", "notification_audit")
    collection = os.environ.get(
        "FIRESTORE_COLLECTION_NOTIFICATION_CONFIGS",
        "notification_configs",
    )
    port = int(os.environ.get("PORT", "8080"))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    store = NotificationConfigStore(project_id=project_id, collection=collection)
    config_loader = NotificationConfigLoader(store=store)
    config_loader.get_channels(force_reload=True)

    router = NotificationRouter(config_loader)
    channel_dispatcher = ChannelDispatcher()
    audit = AuditLogger(project_id, dataset_id=dataset_id, table_id=table_id)
    dispatcher = NotificationDispatcher(
        router, config_loader, channel_dispatcher, audit, store=store
    )

    consumer = NotificationConsumer(
        project_id,
        subscription_id,
        dispatcher,
        loop,
    )
    admin = NotificationAdmin(consumer, router, config_loader, dispatcher, port=port)

    def _shutdown(*_args: object) -> None:
        logger.info("Shutdown requested")
        consumer.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    consumer_thread = threading.Thread(
        target=consumer.run,
        name="notification-consumer",
        daemon=True,
    )
    consumer_thread.start()

    try:
        loop.run_until_complete(_run_admin(admin))
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()
        loop.close()


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)
