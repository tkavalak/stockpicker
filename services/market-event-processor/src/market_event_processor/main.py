"""Market Event Processor entry point."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading

from market_event_processor.admin import MarketEventAdmin
from market_event_processor.consumer import MarketEventConsumer
from market_event_processor.enriched_publisher import EnrichedEventPublisher
from market_event_processor.metrics_calculator import MetricsCalculator
from market_event_processor.window_store import build_window_store

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


async def _verify_store(store) -> bool:
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, store.ping),
            timeout=float(os.environ.get("REDIS_PING_TIMEOUT_SEC", "5")),
        )
    except asyncio.TimeoutError:
        logger.error("Window store ping timed out")
        return False
    except Exception as exc:
        logger.error("Window store ping failed: %s", exc)
        return False


async def _run_service(
    admin: MarketEventAdmin,
    consumer: MarketEventConsumer,
    store,
) -> None:
    """Bind HTTP first so Cloud Run sees PORT=8080, then verify Redis."""
    await admin.start()
    if not await _verify_store(store):
        logger.error(
            "Window store unreachable. For Cloud Run set REDIS_HOST and attach "
            "VPC connector (see market-event-processor/deploy/deploy.sh)."
        )

    consumer_thread = threading.Thread(
        target=consumer.run, name="market-event-consumer", daemon=True
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
        "PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR",
        "market-event-processor-raw-market-events",
    )
    enriched_topic = os.environ.get(
        "PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS", "enriched-market-events"
    )
    port = int(os.environ.get("PORT", "8080"))

    store = build_window_store()
    calculator = MetricsCalculator(store)
    publisher = EnrichedEventPublisher(project_id=project_id, topic_id=enriched_topic)
    consumer = MarketEventConsumer(
        project_id,
        subscription_id,
        calculator,
        publisher,
    )
    admin = MarketEventAdmin(consumer, calculator, port=port)

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
        asyncio.run(_run_service(admin, consumer, store))
    except OSError as exc:
        if exc.errno == 48:
            logger.error(
                "Port %d is already in use. Stop the other process or set PORT=8084",
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
