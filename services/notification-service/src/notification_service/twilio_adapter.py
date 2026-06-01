"""Twilio SMS / WhatsApp delivery."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

from notification_service.models import AlertDecision, DeliveryResult, twilio_message_body

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class TwilioAdapter:
    async def send(
        self,
        decision: AlertDecision,
        *,
        credentials: dict[str, Any] | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> DeliveryResult:
        creds = credentials or {}
        account_sid = str(
            creds.get("account_sid") or os.environ.get("TWILIO_ACCOUNT_SID", "")
        )
        auth_token = str(
            creds.get("auth_token") or os.environ.get("TWILIO_AUTH_TOKEN", "")
        )
        from_number = str(
            creds.get("from_number") or os.environ.get("TWILIO_FROM_NUMBER", "")
        )
        to_number = str(
            creds.get("to_number") or os.environ.get("TWILIO_TO_NUMBER", "")
        )
        mode = str(creds.get("mode") or os.environ.get("TWILIO_MODE", "sms")).lower()

        if not all([account_sid, auth_token, from_number, to_number]):
            return DeliveryResult(
                channel="twilio",
                status="failed",
                http_status=None,
                latency_ms=0,
                error="Twilio not configured",
            )

        if mode == "whatsapp":
            from_number = f"whatsapp:{from_number.lstrip('whatsapp:')}"
            to_number = f"whatsapp:{to_number.lstrip('whatsapp:')}"

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        body = twilio_message_body(decision)
        data = urlencode({"From": from_number, "To": to_number, "Body": body})
        auth = aiohttp.BasicAuth(account_sid, auth_token)

        start = time.monotonic()
        last_status: int | None = None
        last_error: str | None = None

        async with session or aiohttp.ClientSession() as http:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with http.post(
                        url,
                        data=data,
                        auth=auth,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=30,
                    ) as resp:
                        last_status = resp.status
                        latency = int((time.monotonic() - start) * 1000)
                        if 200 <= resp.status < 300:
                            return DeliveryResult(
                                channel="twilio",
                                status="delivered",
                                http_status=last_status,
                                latency_ms=latency,
                            )
                        text = await resp.text()
                        if 400 <= resp.status < 500:
                            return DeliveryResult(
                                channel="twilio",
                                status="failed",
                                http_status=last_status,
                                latency_ms=latency,
                                error=text[:500],
                            )
                        last_error = text[:500]
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last_error = str(exc)
                    if attempt >= MAX_RETRIES:
                        break
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        latency = int((time.monotonic() - start) * 1000)
        return DeliveryResult(
            channel="twilio",
            status="failed",
            http_status=last_status,
            latency_ms=latency,
            error=last_error,
        )
