"""SendGrid HTML email delivery."""

from __future__ import annotations

import asyncio
import logging
import os
import time

import aiohttp

from notification_service.models import AlertDecision, DeliveryResult, email_alert_payload

logger = logging.getLogger(__name__)

SENDGRID_API = "https://api.sendgrid.com/v3/mail/send"
MAX_RETRIES = 3


class EmailAdapter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        from_email: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("SENDGRID_API_KEY", "")
        self._from_email = from_email or os.environ.get("SENDGRID_FROM_EMAIL", "")
        self._session = session

    async def send(
        self,
        decision: AlertDecision,
        *,
        to_email: str | None = None,
        dashboard_url: str | None = None,
    ) -> DeliveryResult:
        recipient = to_email or os.environ.get("ALERT_TO_EMAIL", "")
        if not self._api_key or not self._from_email or not recipient:
            return DeliveryResult(
                channel="email",
                status="failed",
                http_status=None,
                latency_ms=0,
                error="SendGrid not configured",
            )

        content = email_alert_payload(
            decision,
            dashboard_url=dashboard_url or os.environ.get("DASHBOARD_URL", "#"),
        )
        payload = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": self._from_email},
            "subject": content["subject"],
            "content": [{"type": "text/html", "value": content["html"]}],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        last_status: int | None = None
        last_error: str | None = None

        async with self._session or aiohttp.ClientSession() as session:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with session.post(
                        SENDGRID_API, json=payload, headers=headers, timeout=30
                    ) as resp:
                        last_status = resp.status
                        latency = int((time.monotonic() - start) * 1000)
                        if 200 <= resp.status < 300:
                            return DeliveryResult(
                                channel="email",
                                status="delivered",
                                http_status=last_status,
                                latency_ms=latency,
                            )
                        body = await resp.text()
                        if 400 <= resp.status < 500:
                            return DeliveryResult(
                                channel="email",
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
            channel="email",
            status="failed",
            http_status=last_status,
            latency_ms=latency,
            error=last_error,
        )
