"""Microsoft Teams Incoming Webhook delivery (Adaptive Card)."""

from __future__ import annotations

import asyncio
import logging
import time

import aiohttp

from notification_service.models import AlertDecision, DeliveryResult, teams_alert_card

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class TeamsAdapter:
    async def send(
        self,
        decision: AlertDecision,
        *,
        webhook_url: str,
        session: aiohttp.ClientSession | None = None,
    ) -> DeliveryResult:
        if not webhook_url:
            return DeliveryResult(
                channel="teams",
                status="failed",
                http_status=None,
                latency_ms=0,
                error="Teams webhook URL not configured",
            )

        payload = teams_alert_card(decision)
        start = time.monotonic()
        last_status: int | None = None
        last_error: str | None = None

        async with session or aiohttp.ClientSession() as http:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with http.post(
                        webhook_url, json=payload, timeout=30
                    ) as resp:
                        last_status = resp.status
                        latency = int((time.monotonic() - start) * 1000)
                        if 200 <= resp.status < 300:
                            return DeliveryResult(
                                channel="teams",
                                status="delivered",
                                http_status=last_status,
                                latency_ms=latency,
                            )
                        body = await resp.text()
                        if 400 <= resp.status < 500:
                            return DeliveryResult(
                                channel="teams",
                                status="failed",
                                http_status=last_status,
                                latency_ms=latency,
                                error=body[:500],
                            )
                        last_error = body[:500]
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last_error = str(exc)
                    if attempt >= MAX_RETRIES:
                        break
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        latency = int((time.monotonic() - start) * 1000)
        return DeliveryResult(
            channel="teams",
            status="failed",
            http_status=last_status,
            latency_ms=latency,
            error=last_error,
        )
