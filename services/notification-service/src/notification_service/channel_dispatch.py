"""Dispatch alerts to a single channel (used by dispatcher and channel API)."""

from __future__ import annotations

import logging
from typing import Any

from notification_service.channels import (
    CHANNEL_EMAIL,
    CHANNEL_PUSHOVER,
    CHANNEL_SLACK,
    CHANNEL_TEAMS,
    CHANNEL_TWILIO,
    ChannelRecord,
)
from notification_service.email_adapter import EmailAdapter
from notification_service.models import AlertDecision, DeliveryResult
from notification_service.pushover_adapter import PushoverAdapter
from notification_service.slack_adapter import SlackAdapter
from notification_service.teams_adapter import TeamsAdapter
from notification_service.twilio_adapter import TwilioAdapter

logger = logging.getLogger(__name__)


class ChannelDispatcher:
    def __init__(
        self,
        *,
        slack: SlackAdapter | None = None,
        email: EmailAdapter | None = None,
        teams: TeamsAdapter | None = None,
        twilio: TwilioAdapter | None = None,
        pushover: PushoverAdapter | None = None,
    ) -> None:
        self._slack = slack or SlackAdapter()
        self._email = email or EmailAdapter()
        self._teams = teams or TeamsAdapter()
        self._twilio = twilio or TwilioAdapter()
        self._pushover = pushover or PushoverAdapter()

    async def send_to_channel(
        self,
        channel_type: str,
        decision: AlertDecision,
        record: ChannelRecord,
    ) -> DeliveryResult:
        creds = record.credentials
        if channel_type == CHANNEL_EMAIL:
            return await self._email.send(
                decision,
                to_email=creds.get("to_email"),
            )
        if channel_type == CHANNEL_TEAMS:
            return await self._teams.send(
                decision, webhook_url=str(creds.get("webhook_url") or "")
            )
        if channel_type == CHANNEL_TWILIO:
            return await self._twilio.send(decision, credentials=creds)
        if channel_type == CHANNEL_SLACK:
            return await self._slack.send(
                decision, channel_id=str(creds.get("channel_id") or "")
            )
        if channel_type == CHANNEL_PUSHOVER:
            return await self._pushover.send(decision, credentials=creds)
        return DeliveryResult(
            channel=channel_type,
            status="failed",
            http_status=None,
            latency_ms=0,
            error=f"unknown channel: {channel_type}",
        )
