"""HTTP admin: health and channel management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

from notification_service.channel_api import register_channel_routes

if TYPE_CHECKING:
    from notification_service.config_loader import NotificationConfigLoader
    from notification_service.consumer import NotificationConsumer
    from notification_service.dispatcher import NotificationDispatcher
    from notification_service.router import NotificationRouter

logger = logging.getLogger(__name__)


class NotificationAdmin:
    def __init__(
        self,
        consumer: NotificationConsumer,
        router: NotificationRouter,
        config_loader: NotificationConfigLoader,
        dispatcher: NotificationDispatcher,
        port: int = 8080,
    ) -> None:
        self._consumer = consumer
        self._router = router
        self._port = port
        self._app = web.Application()
        self._app.router.add_get("/health", self._health)
        register_channel_routes(
            self._app,
            config_loader=config_loader,
            dispatcher=dispatcher,
        )
        self._runner: web.AppRunner | None = None

    async def _health(self, request: web.Request) -> web.Response:
        if not self._consumer.healthy:
            return web.json_response({"status": "unavailable"}, status=503)
        return web.json_response(
            {
                "status": "ok",
                "messages_processed": self._consumer.messages_processed,
                "channels": self._router.config_snapshot(),
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
