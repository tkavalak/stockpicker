from unittest.mock import MagicMock

from notification_service.channels import (
    CHANNEL_EMAIL,
    CHANNEL_TEAMS,
    STATUS_CONNECTED,
    ChannelRecord,
)
from notification_service.config_loader import NotificationConfigLoader
from notification_service.config_store import NotificationConfigStore
from notification_service.models import ACTION_IGNORE, AlertDecision
from notification_service.router import NotificationRouter


def _decision(action: str = "ALERT") -> AlertDecision:
    return AlertDecision(
        decision_id="d1",
        symbol="AAPL",
        action=action,
        signal_type="PRICE_SPIKE_5M",
        measured_magnitude=2.5,
        confidence_score=0.9,
        reason="test",
        event_timestamp="2026-01-01T00:00:00Z",
    )


def test_ignore_returns_no_channels():
    store = MagicMock(spec=NotificationConfigStore)
    store.get_channels.return_value = {
        CHANNEL_EMAIL: ChannelRecord(
            channel_type=CHANNEL_EMAIL,
            status=STATUS_CONNECTED,
            enabled=True,
            consecutive_failures=0,
            last_verified_at=None,
            routing_rule=None,
            credentials={"to_email": "a@b.com"},
        )
    }
    loader = NotificationConfigLoader(store=store)
    loader._channels = store.get_channels()
    loader._loaded_at = 0
    router = NotificationRouter(loader)
    assert router.channels_for(_decision(ACTION_IGNORE)) == []


def test_deliverable_email_channel():
    store = MagicMock(spec=NotificationConfigStore)
    store.get_channels.return_value = {
        CHANNEL_EMAIL: ChannelRecord(
            channel_type=CHANNEL_EMAIL,
            status=STATUS_CONNECTED,
            enabled=True,
            consecutive_failures=0,
            last_verified_at=None,
            routing_rule=None,
            credentials={"to_email": "user@test.com"},
        ),
        CHANNEL_TEAMS: ChannelRecord(
            channel_type=CHANNEL_TEAMS,
            status=STATUS_CONNECTED,
            enabled=False,
            consecutive_failures=0,
            last_verified_at=None,
            routing_rule=None,
            credentials={},
        ),
    }
    loader = NotificationConfigLoader(store=store)
    loader._channels = store.get_channels()
    loader._loaded_at = 0
    router = NotificationRouter(loader)
    channels = router.channels_for(_decision("ALERT"))
    assert CHANNEL_EMAIL in channels
    assert CHANNEL_TEAMS not in channels
