"""HTTP admin endpoints for health and symbol listing."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from polygon_streamer.stream_listener import PolygonStreamListener

logger = logging.getLogger(__name__)


class StreamAdminController:
    def __init__(self, listener: PolygonStreamListener, port: int = 8080) -> None:
        self._listener = listener
        self._port = port
        self._app = web.Application()
        self._app.router.add_get("/health", self._health)
        self._app.router.add_get("/symbols", self._symbols)
        self._runner: web.AppRunner | None = None

    async def _health(self, request: web.Request) -> web.Response:
        if self._listener.connected:
            return web.json_response({"status": "ok", "websocket": "connected"})
        body = {
            "status": "unavailable",
            "websocket": "disconnected",
        }
        elapsed = self._listener.disconnected_seconds
        if elapsed is not None:
            body["disconnected_seconds"] = round(elapsed, 1)
        return web.json_response(body, status=503)

    async def _symbols(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "symbols": self._listener.symbols,
                "subscriptions": self._listener.subscriptions,
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
