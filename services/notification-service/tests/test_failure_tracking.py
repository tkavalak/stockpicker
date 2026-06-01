from unittest.mock import MagicMock

from notification_service.channels import CHANNEL_EMAIL, STATUS_CONNECTED, STATUS_ERROR
from notification_service.channels import ChannelRecord
from notification_service.config_store import NotificationConfigStore


def _email_record(**kwargs) -> ChannelRecord:
    base = ChannelRecord(
        channel_type=CHANNEL_EMAIL,
        status=STATUS_CONNECTED,
        enabled=True,
        consecutive_failures=0,
        last_verified_at=None,
        routing_rule=None,
        credentials={"to_email": "a@b.com"},
    )
    return ChannelRecord(
        channel_type=base.channel_type,
        status=kwargs.get("status", base.status),
        enabled=base.enabled,
        consecutive_failures=kwargs.get("consecutive_failures", base.consecutive_failures),
        last_verified_at=base.last_verified_at,
        routing_rule=base.routing_rule,
        credentials=base.credentials,
    )


def test_three_failures_set_error():
    client = MagicMock()
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        "channels": {
            CHANNEL_EMAIL: _email_record(consecutive_failures=2).to_firestore_dict(),
        }
    }
    client.collection.return_value.document.return_value.get.return_value = doc

    store = NotificationConfigStore(client=client)
    updated = store.record_delivery_outcome(CHANNEL_EMAIL, success=False, error="timeout")
    assert updated.consecutive_failures == 3
    assert updated.status == STATUS_ERROR


def test_success_resets_failures():
    client = MagicMock()
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        "channels": {
            CHANNEL_EMAIL: _email_record(
                consecutive_failures=2, status=STATUS_CONNECTED
            ).to_firestore_dict(),
        }
    }
    client.collection.return_value.document.return_value.get.return_value = doc

    store = NotificationConfigStore(client=client)
    updated = store.record_delivery_outcome(CHANNEL_EMAIL, success=True)
    assert updated.consecutive_failures == 0
    assert updated.status == STATUS_CONNECTED
    assert updated.last_verified_at is not None
