"""Pushover mobile/desktop notification delivery."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

from notification_service.models import (
    ACTION_ESCALATE,
    AlertDecision,
    DeliveryResult,
    pushover_message_body,
    pushover_title,
)

logger = logging.getLogger(__name__)

PUSHOVER_API = "https://api.pushover.net/1/messages.json"
MAX_RETRIES = 3


class PushoverAdapter:
    async def send(
        self,
        decision: AlertDecision,
        *,
        credentials: dict[str, Any] | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> DeliveryResult:
        creds = credentials or {}
        app_token = str(
            creds.get("app_token") or os.environ.get("PUSHOVER_APP_TOKEN", "")
        )
        user_key = str(
            creds.get("user_key") or os.environ.get("PUSHOVER_USER_KEY", "")
        )
        device = str(creds.get("device") or os.environ.get("PUSHOVER_DEVICE", ""))

        if not app_token or not user_key:
            return DeliveryResult(
                channel="pushover",
                status="failed",
                http_status=None,
                latency_ms=0,
                error="Pushover not configured (PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY)",
            )

        priority = "1" if decision.action == ACTION_ESCALATE else "0"
        if creds.get("priority") is not None:
            priority = str(creds.get("priority"))

        payload: dict[str, str] = {
            "token": app_token,
            "user": user_key,
            "title": pushover_title(decision),
            "message": pushover_message_body(decision),
            "priority": priority,
        }
        if device:
            payload["device"] = device

        data = urlencode(payload)
        start = time.monotonic()
        last_status: int | None = None
        last_error: str | None = None

        async with session or aiohttp.ClientSession() as http:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    async with http.post(
                        PUSHOVER_API,
                        data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=30,
                    ) as resp:
                        last_status = resp.status
                        latency = int((time.monotonic() - start) * 1000)
                        body = await resp.text()
                        if resp.status == 200:
                            return DeliveryResult(
                                channel="pushover",
                                status="delivered",
                                http_status=last_status,
                                latency_ms=latency,
                            )
                        if 400 <= resp.status < 500:
                            return DeliveryResult(
                                channel="pushover",
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
            channel="pushover",
            status="failed",
            http_status=last_status,
            latency_ms=latency,
            error=last_error,
        )
