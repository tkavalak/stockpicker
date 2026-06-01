"""Firestore persistence for notification channel configuration."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from notification_service.channels import (
    ALL_CHANNEL_TYPES,
    CHANNEL_EMAIL,
    CHANNEL_PUSHOVER,
    CHANNEL_SLACK,
    CHANNEL_TEAMS,
    CHANNEL_TWILIO,
    STATUS_CONNECTED,
    STATUS_DISCONNECTED,
    ChannelRecord,
    RoutingRule,
)

logger = logging.getLogger(__name__)

CONFIG_DOC_ID = "default"


class NotificationConfigStore:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        collection: str | None = None,
        client: firestore.Client | None = None,
    ) -> None:
        self._client = client or firestore.Client(project=project_id)
        self._collection = collection or os.environ.get(
            "FIRESTORE_COLLECTION_NOTIFICATION_CONFIGS",
            "notification_configs",
        )

    def _doc_ref(self) -> firestore.DocumentReference:
        return self._client.collection(self._collection).document(CONFIG_DOC_ID)

    def _load_raw(self) -> dict[str, Any]:
        doc = self._doc_ref().get()
        if not doc.exists:
            return {}
        return doc.to_dict() or {}

    def _ensure_channels_blob(self, data: dict[str, Any]) -> dict[str, Any]:
        if "channels" in data and isinstance(data["channels"], dict):
            return data["channels"]
        return _migrate_legacy_channels(data)

    def get_channels(self) -> dict[str, ChannelRecord]:
        data = self._load_raw()
        blob = self._ensure_channels_blob(data)
        return {
            ch_type: ChannelRecord.from_firestore_dict(ch_type, blob.get(ch_type))
            for ch_type in ALL_CHANNEL_TYPES
        }

    def get_channel(self, channel_type: str) -> ChannelRecord:
        if channel_type not in ALL_CHANNEL_TYPES:
            raise ValueError(f"unknown channel type: {channel_type}")
        return self.get_channels()[channel_type]

    def save_channels(self, channels: dict[str, ChannelRecord]) -> None:
        blob = {k: v.to_firestore_dict() for k, v in channels.items()}
        self._doc_ref().set({"channels": blob}, merge=True)

    def upsert_channel(self, record: ChannelRecord) -> None:
        channels = self.get_channels()
        channels[record.channel_type] = record
        self.save_channels(channels)

    def connect_channel(
        self,
        channel_type: str,
        *,
        credentials: dict[str, Any],
        routing_rule: RoutingRule | None = None,
        enabled: bool = True,
    ) -> ChannelRecord:
        record = ChannelRecord(
            channel_type=channel_type,
            status=STATUS_CONNECTED,
            enabled=enabled,
            consecutive_failures=0,
            last_verified_at=None,
            routing_rule=routing_rule,
            credentials=credentials,
        )
        self.upsert_channel(record)
        return record

    def disconnect_channel(self, channel_type: str) -> ChannelRecord:
        record = self.get_channel(channel_type)
        updated = ChannelRecord(
            channel_type=record.channel_type,
            status=STATUS_DISCONNECTED,
            enabled=False,
            consecutive_failures=0,
            last_verified_at=record.last_verified_at,
            routing_rule=record.routing_rule,
            credentials={},
        )
        self.upsert_channel(updated)
        return updated

    def update_routing_rule(
        self, channel_type: str, routing_rule: RoutingRule | None
    ) -> ChannelRecord:
        record = self.get_channel(channel_type)
        updated = ChannelRecord(
            channel_type=record.channel_type,
            status=record.status,
            enabled=record.enabled,
            consecutive_failures=record.consecutive_failures,
            last_verified_at=record.last_verified_at,
            routing_rule=routing_rule,
            credentials=record.credentials,
        )
        self.upsert_channel(updated)
        return updated

    def record_delivery_outcome(
        self, channel_type: str, *, success: bool, error: str | None = None
    ) -> ChannelRecord:
        record = self.get_channel(channel_type)
        now = datetime.now(timezone.utc).isoformat()
        if success:
            updated = ChannelRecord(
                channel_type=record.channel_type,
                status=STATUS_CONNECTED,
                enabled=record.enabled,
                consecutive_failures=0,
                last_verified_at=now,
                routing_rule=record.routing_rule,
                credentials=record.credentials,
            )
        else:
            failures = record.consecutive_failures + 1
            from notification_service.channels import CONSECUTIVE_FAILURE_LIMIT, STATUS_ERROR

            status = (
                STATUS_ERROR
                if failures >= CONSECUTIVE_FAILURE_LIMIT
                else record.status
            )
            updated = ChannelRecord(
                channel_type=record.channel_type,
                status=status,
                enabled=record.enabled,
                consecutive_failures=failures,
                last_verified_at=record.last_verified_at,
                routing_rule=record.routing_rule,
                credentials=record.credentials,
            )
            if status == STATUS_ERROR:
                logger.error(
                    "Channel %s marked error after %d consecutive failures: %s",
                    channel_type,
                    failures,
                    error,
                )
        self.upsert_channel(updated)
        return updated

    def mark_verified(self, channel_type: str) -> ChannelRecord:
        record = self.get_channel(channel_type)
        updated = ChannelRecord(
            channel_type=record.channel_type,
            status=STATUS_CONNECTED,
            enabled=record.enabled,
            consecutive_failures=0,
            last_verified_at=datetime.now(timezone.utc).isoformat(),
            routing_rule=record.routing_rule,
            credentials=record.credentials,
        )
        self.upsert_channel(updated)
        return updated

    def mark_test_failed(self, channel_type: str, error: str) -> ChannelRecord:
        record = self.get_channel(channel_type)
        from notification_service.channels import STATUS_ERROR

        updated = ChannelRecord(
            channel_type=record.channel_type,
            status=STATUS_ERROR,
            enabled=record.enabled,
            consecutive_failures=record.consecutive_failures,
            last_verified_at=record.last_verified_at,
            routing_rule=record.routing_rule,
            credentials=record.credentials,
        )
        self.upsert_channel(updated)
        logger.warning("Channel %s test failed: %s", channel_type, error)
        return updated


def _migrate_legacy_channels(data: dict[str, Any]) -> dict[str, Any]:
    """Build channels map from WO-8 flat notification_configs fields."""
    slack_enabled = bool(
        data.get("slack_enabled", bool(os.environ.get("SLACK_BOT_TOKEN")))
    )
    email_enabled = bool(
        data.get("email_enabled", bool(os.environ.get("SENDGRID_API_KEY")))
    )
    pushover_enabled = bool(
        data.get(
            "pushover_enabled",
            bool(
                os.environ.get("PUSHOVER_APP_TOKEN")
                and os.environ.get("PUSHOVER_USER_KEY")
            ),
        )
    )
    return {
        CHANNEL_SLACK: {
            "status": STATUS_CONNECTED if slack_enabled else STATUS_DISCONNECTED,
            "enabled": slack_enabled,
            "consecutive_failures": 0,
            "credentials": {
                "channel_id": data.get("slack_channel_id")
                or os.environ.get("SLACK_CHANNEL_ID", ""),
            },
        },
        CHANNEL_EMAIL: {
            "status": STATUS_CONNECTED if email_enabled else STATUS_DISCONNECTED,
            "enabled": email_enabled,
            "consecutive_failures": 0,
            "credentials": {
                "to_email": data.get("email_to") or os.environ.get("ALERT_TO_EMAIL", ""),
                "from_email": data.get("email_from")
                or os.environ.get("SENDGRID_FROM_EMAIL", ""),
            },
        },
        CHANNEL_TEAMS: {"status": STATUS_DISCONNECTED, "enabled": False, "credentials": {}},
        CHANNEL_TWILIO: {"status": STATUS_DISCONNECTED, "enabled": False, "credentials": {}},
        CHANNEL_PUSHOVER: {
            "status": STATUS_CONNECTED if pushover_enabled else STATUS_DISCONNECTED,
            "enabled": pushover_enabled,
            "consecutive_failures": 0,
            "credentials": {
                "user_key": os.environ.get("PUSHOVER_USER_KEY", ""),
            },
        },
    }
