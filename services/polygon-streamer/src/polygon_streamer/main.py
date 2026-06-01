"""Entry point for the Polygon WebSocket Streamer Cloud Run service."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from polygon_streamer.admin import StreamAdminController
from polygon_streamer.pubsub_publisher import PubSubPublisher
from polygon_streamer.single_instance import SingleInstanceError, single_instance
from polygon_streamer.stream_listener import PolygonStreamListener, parse_polygon_feed, parse_watched_symbols

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


async def _run() -> None:
    api_key = _env("POLYGON_API_KEY")
    project_id = _env("GCP_PROJECT_ID")
    topic_id = os.environ.get(
        "PUBSUB_TOPIC_RAW_MARKET_EVENTS",
        "raw-market-events",
    )
    symbols = parse_watched_symbols(_env("WATCHED_SYMBOLS"))
    port = int(os.environ.get("PORT", "8080"))

    publisher = PubSubPublisher(project_id=project_id, topic_id=topic_id)
    listener = PolygonStreamListener(
        api_key,
        symbols,
        publisher,
        feed=parse_polygon_feed(),
    )
    admin = StreamAdminController(listener, port=port)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, listener.request_stop)

    await admin.start()
    try:
        await listener.run()
    finally:
        await admin.stop()


def main() -> None:
    try:
        with single_instance():
            asyncio.run(_run())
    except SingleInstanceError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
