"""Slack Block Kit delivery via Bot API."""

from __future__ import annotations

import logging
import os

# import asyncio
# import time
# import aiohttp

from notification_service.models import (
    ACTION_ESCALATE,
    AlertDecision,
    DeliveryResult,
    slack_alert_payload,
)

logger = logging.getLogger(__name__)

# SLACK_API = "https://slack.com/api/chat.postMessage"
# MAX_RETRIES = 3


class SlackAdapter:
    def __init__(
        self,
        *,
        bot_token: str | None = None,
        channel_id: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        self._default_channel = channel_id or os.environ.get("SLACK_CHANNEL_ID", "")
        self._session = session

    async def send(
        self,
        decision: AlertDecision,
        *,
        channel_id: str | None = None,
    ) -> DeliveryResult:
        """
        Log Slack alert details only. chat.postMessage is disabled until configured.

        To enable: set slack_enabled in Firestore, uncomment the HTTP block below,
        and set SLACK_BOT_TOKEN + SLACK_CHANNEL_ID (or deploy secrets).
        """
        channel = channel_id or self._default_channel
        body = slack_alert_payload(decision)
        if decision.action == ACTION_ESCALATE:
            body["text"] = f"<!channel> {body['text']}"

        logger.info(
            "SLACK alert (not sent): symbol=%s action=%s channel=%s text=%s",
            decision.symbol,
            decision.action,
            channel or "(none)",
            body.get("text", ""),
        )
        return DeliveryResult(
            channel="slack",
            status="skipped",
            http_status=None,
            latency_ms=0,
            error=None,
        )

        # --- Slack API delivery (disabled) ---
        # if not self._token or not channel:
        #     return DeliveryResult(
        #         channel="slack",
        #         status="failed",
        #         http_status=None,
        #         latency_ms=0,
        #         error="Slack not configured",
        #     )
        #
        # payload = {"channel": channel, **body}
        # headers = {
        #     "Authorization": f"Bearer {self._token}",
        #     "Content-Type": "application/json",
        # }
        #
        # start = time.monotonic()
        # last_status: int | None = None
        # last_error: str | None = None
        #
        # async with self._session or aiohttp.ClientSession() as session:
        #     for attempt in range(1, MAX_RETRIES + 1):
        #         try:
        #             async with session.post(
        #                 SLACK_API, json=payload, headers=headers, timeout=30
        #             ) as resp:
        #                 last_status = resp.status
        #                 data = await resp.json(content_type=None)
        #                 latency = int((time.monotonic() - start) * 1000)
        #                 if resp.status == 200 and data.get("ok"):
        #                     return DeliveryResult(
        #                         channel="slack",
        #                         status="delivered",
        #                         http_status=200,
        #                         latency_ms=latency,
        #                     )
        #                 if 400 <= resp.status < 500:
        #                     return DeliveryResult(
        #                         channel="slack",
        #                         status="failed",
        #                         http_status=last_status,
        #                         latency_ms=latency,
        #                         error=str(data),
        #                     )
        #                 last_error = str(data)
        #         except (aiohttp.ClientError, TimeoutError) as exc:
        #             last_error = str(exc)
        #             if attempt >= MAX_RETRIES:
        #                 break
        #             await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
        #
        # latency = int((time.monotonic() - start) * 1000)
        # return DeliveryResult(
        #     channel="slack",
        #     status="failed",
        #     http_status=last_status,
        #     latency_ms=latency,
        #     error=last_error,
        # )
