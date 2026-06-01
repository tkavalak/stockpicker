from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from agentic_ai.governance.cooldown import CooldownStore, cooldown_document_id


def test_cooldown_document_id():
    assert cooldown_document_id("aapl", "volume_spike") == "AAPL_VOLUME_SPIKE"


def test_is_in_cooldown_when_recent():
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        "last_alerted_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
    }
    client = MagicMock()
    client.collection.return_value.document.return_value.get.return_value = doc
    store = CooldownStore(client=client, default_window_minutes=10.0)
    assert store.is_in_cooldown("AAPL", "PRICE_SPIKE_5M") is True


def test_not_in_cooldown_when_expired():
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = {
        "last_alerted_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat(),
    }
    client = MagicMock()
    client.collection.return_value.document.return_value.get.return_value = doc
    store = CooldownStore(client=client, default_window_minutes=10.0)
    assert store.is_in_cooldown("AAPL", "PRICE_SPIKE_5M") is False
