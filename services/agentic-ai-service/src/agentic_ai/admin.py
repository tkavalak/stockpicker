"""Admin HTTP: /health and /metrics."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web

if TYPE_CHECKING:
    from agentic_ai.consumer import TriggerEventConsumer
    from agentic_ai.governance.thresholds import GovernanceThresholds
    from agentic_ai.orchestrator import AgentOrchestrator
    from agentic_ai.publisher import AlertDecisionPublisher

logger = logging.getLogger(__name__)


class AgenticAIAdmin:
    def __init__(
        self,
        consumer: TriggerEventConsumer,
        orchestrator: AgentOrchestrator,
        publisher: AlertDecisionPublisher,
        thresholds: GovernanceThresholds,
        port: int = 8080,
    ) -> None:
        self._consumer = consumer
        self._orchestrator = orchestrator
        self._publisher = publisher
        self._thresholds = thresholds
        self._port = port
        self._app = web.Application()
        self._app.router.add_get("/health", self._health)
        self._app.router.add_get("/metrics", self._metrics)
        self._runner: web.AppRunner | None = None

    async def _health(self, request: web.Request) -> web.Response:
        status = "ok" if self._consumer.healthy else "degraded"
        code = 200 if self._consumer.healthy else 503
        return web.json_response(
            {
                "status": status,
                "messages_processed": self._consumer.messages_processed,
            },
            status=code,
        )

    async def _metrics(self, request: web.Request) -> web.Response:
        return web.json_response(
            {
                "messages_processed": self._consumer.messages_processed,
                "orchestrator": self._orchestrator.metrics,
                "alerts_published": self._publisher.published_count,
                "governance": {
                    "confidence_threshold": self._thresholds.confidence_threshold,
                    "escalation_threshold": self._thresholds.escalation_threshold,
                    "cooldown_minutes": self._thresholds.cooldown_minutes,
                },
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
