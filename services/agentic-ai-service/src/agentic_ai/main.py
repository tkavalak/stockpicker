"""Agentic AI Service entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading

from agentic_ai.admin import AgenticAIAdmin
from agentic_ai.agents.control_agent import set_governance_thresholds
from agentic_ai.consumer import TriggerEventConsumer
from agentic_ai.governance.cooldown import CooldownStore, set_cooldown_store
from agentic_ai.governance.thresholds import load_governance_thresholds
from agentic_ai.idempotency import AgentStateStore
from agentic_ai.orchestrator import AgentOrchestrator
from agentic_ai.publisher import AlertDecisionPublisher

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


async def _run_service(
    admin: AgenticAIAdmin, consumer: TriggerEventConsumer
) -> None:
    await admin.start()
    consumer_thread = threading.Thread(
        target=consumer.run, name="agentic-ai-consumer", daemon=True
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
        "PUBSUB_SUBSCRIPTION_AGENTIC_AI",
        "agentic-ai-trigger-events",
    )
    alert_topic = os.environ.get("PUBSUB_TOPIC_ALERT_DECISIONS", "alert-decisions")
    agent_collection = os.environ.get("FIRESTORE_COLLECTION_AGENT_STATE", "agent_state")
    port = int(os.environ.get("PORT", "8080"))

    thresholds = load_governance_thresholds()
    set_governance_thresholds(thresholds)
    set_cooldown_store(
        CooldownStore(
            project_id=project_id,
            collection=agent_collection,
            default_window_minutes=thresholds.cooldown_minutes,
        )
    )
    logger.info(
        "Governance: confidence=%.2f escalation=%.2f cooldown=%.0f min",
        thresholds.confidence_threshold,
        thresholds.escalation_threshold,
        thresholds.cooldown_minutes,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    state_store = AgentStateStore(project_id=project_id, collection=agent_collection)
    orchestrator = AgentOrchestrator(state_store=state_store)
    publisher = AlertDecisionPublisher(project_id, alert_topic)
    consumer = TriggerEventConsumer(
        project_id,
        subscription_id,
        orchestrator,
        publisher,
        loop,
    )
    admin = AgenticAIAdmin(
        consumer, orchestrator, publisher, thresholds, port=port
    )

    def _shutdown(*_args: object) -> None:
        logger.info("Shutdown requested")
        consumer.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        loop.run_until_complete(_run_service(admin, consumer))
    except OSError as exc:
        if exc.errno == 48:
            logger.error(
                "Port %d is already in use. Stop the other process or set PORT=8082",
                port,
            )
            sys.exit(1)
        raise
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
