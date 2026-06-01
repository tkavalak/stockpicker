"""Admin HTTP: /health and /rules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from rule_engine.consumer import RuleEngineConsumer
    from rule_engine.rule_config_loader import RuleConfigLoader

logger = logging.getLogger(__name__)


class RuleEngineAdmin:
    def __init__(
        self,
        config_loader: RuleConfigLoader,
        consumer: RuleEngineConsumer,
        port: int = 8080,
    ) -> None:
        self._config_loader = config_loader
        self._consumer = consumer
        self._port = port
        self._app = web.Application()
        self._app.router.add_get("/health", self._health)
        self._app.router.add_get("/rules", self._rules)
        self._runner: web.AppRunner | None = None

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "messages_processed": self._consumer.messages_processed,
                "triggers_published": self._consumer.triggers_published,
                "config_cache_age_sec": round(self._config_loader.cache_age_seconds, 1),
            }
        )

    async def _rules(self, request: web.Request) -> web.Response:
        rules = self._config_loader.configs_for_admin()
        return web.json_response(
            {
                "rules": rules,
                "cache_ttl_sec": 30,
                "cache_age_sec": round(self._config_loader.cache_age_seconds, 1),
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
