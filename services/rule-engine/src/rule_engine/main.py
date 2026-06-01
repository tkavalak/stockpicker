"""Rule Engine Service entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading

from rule_engine.admin import RuleEngineAdmin
from rule_engine.consumer import RuleEngineConsumer
from rule_engine.rule_config_loader import RuleConfigLoader
from rule_engine.trigger_publisher import TriggerEventPublisher

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


async def _run_service(admin: RuleEngineAdmin, consumer: RuleEngineConsumer) -> None:
    """Bind admin HTTP first, then start Pub/Sub consumer (avoids orphaned gRPC on port errors)."""
    await admin.start()
    consumer_thread = threading.Thread(
        target=consumer.run, name="rule-engine-consumer", daemon=True
    )
    consumer_thread.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        consumer.stop()
        consumer_thread.join(timeout=5)
        await admin.stop()


def main() -> None:
    project_id = _env("GCP_PROJECT_ID")
    subscription_id = os.environ.get(
        "PUBSUB_SUBSCRIPTION_RULE_ENGINE",
        "rule-engine-enriched-market-events",
    )
    trigger_topic = os.environ.get("PUBSUB_TOPIC_TRIGGER_EVENTS", "trigger-events")
    collection = os.environ.get("FIRESTORE_COLLECTION_RULE_CONFIGS", "rule_configs")
    port = int(os.environ.get("PORT", "8080"))

    config_loader = RuleConfigLoader(project_id=project_id, collection=collection)
    config_loader.get_configs(force_reload=True)

    trigger_publisher = TriggerEventPublisher(project_id=project_id, topic_id=trigger_topic)
    consumer = RuleEngineConsumer(
        project_id=project_id,
        subscription_id=subscription_id,
        config_loader=config_loader,
        trigger_publisher=trigger_publisher,
    )
    admin = RuleEngineAdmin(config_loader, consumer, port=port)

    shutting_down = False

    def _shutdown(*_args: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        logger.info("Shutdown requested")
        consumer.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        asyncio.run(_run_service(admin, consumer))
    except OSError as exc:
        if exc.errno == 48:
            logger.error(
                "Port %d is already in use. Stop the other process (lsof -i :%d) "
                "or run with PORT=8081 ./services/rule-engine/run.sh",
                port,
                port,
            )
            sys.exit(1)
        raise
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)
