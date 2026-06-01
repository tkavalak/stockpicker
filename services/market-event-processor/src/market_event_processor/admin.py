"""Admin HTTP: /health."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from market_event_processor.consumer import MarketEventConsumer
    from market_event_processor.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)


class MarketEventAdmin:
    def __init__(
        self,
        consumer: MarketEventConsumer,
        calculator: MetricsCalculator,
        port: int = 8080,
    ) -> None:
        self._consumer = consumer
        self._calculator = calculator
        self._port = port
        self._app = web.Application()
        self._app.router.add_get("/health", self._health)
        self._runner: web.AppRunner | None = None

    async def _health(self, request: web.Request) -> web.Response:
        store = self._calculator.store
        redis_ok = True
        storage = "memory"
        try:
            redis_ok = store.ping()
            storage = (
                "redis"
                if type(store).__name__ == "RedisWindowStore"
                else "memory"
            )
        except Exception as exc:
            logger.warning("Window store health check failed: %s", exc)
            redis_ok = False

        if not redis_ok:
            return web.json_response(
                {
                    "status": "unavailable",
                    "storage": storage,
                    "redis_ok": False,
                    "consumer_running": self._consumer.healthy,
                },
                status=503,
            )

        return web.json_response(
            {
                "status": "ok",
                "storage": storage,
                "redis_ok": True,
                "consumer_running": self._consumer.healthy,
                "messages_processed": self._consumer.messages_processed,
                "messages_published": self._consumer.messages_published,
            }
        )

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Admin HTTP listening on :%d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
