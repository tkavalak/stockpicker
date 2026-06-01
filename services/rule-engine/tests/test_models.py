import json

import pytest

from rule_engine.models import (
    EnrichedMarketEvent,
    RuleConfig,
    build_trigger_envelope,
    parse_enriched_pubsub_message,
)


def test_parse_enriched_envelope():
    envelope = {
        "message_id": "msg-123",
        "source_container": "market-event-processor",
        "topic": "enriched-market-events",
        "published_at": "2026-01-01T00:00:00Z",
        "schema_version": "1.0",
        "payload": {
            "symbol": "NVDA",
            "event_type": "aggregate",
            "price": 500.0,
            "volume": 100.0,
            "timestamp_ns": 999,
            "raw_payload": {},
            "pct_change_5m": 2.1,
            "volume_ratio": 3.5,
        },
    }
    msg_id, event, full = parse_enriched_pubsub_message(json.dumps(envelope).encode())
    assert msg_id == "msg-123"
    assert event.symbol == "NVDA"
    assert event.pct_change_5m == 2.1
    assert full["message_id"] == "msg-123"


def test_parse_rejects_invalid_json():
    with pytest.raises(ValueError):
        parse_enriched_pubsub_message(b"not-json")


def test_rule_config_from_firestore():
    cfg = RuleConfig.from_firestore(
        {
            "rule_name": "PRICE_SPIKE_5M",
            "enabled": True,
            "threshold": 2.5,
            "symbols": ["AAPL", "TSLA"],
        }
    )
    assert cfg.threshold == 2.5
    assert "AAPL" in cfg.symbols


def test_trigger_envelope_shape():
    from rule_engine.models import TriggerEvent

    trigger = TriggerEvent(
        event_id="e1",
        symbol="AAPL",
        rule_name="VOLUME_SPIKE",
        triggered_value=4.0,
        threshold_value=3.0,
        enriched_event={"payload": {}},
        fired_at="2026-01-01T00:00:00Z",
    )
    env = build_trigger_envelope(trigger, topic="trigger-events")
    assert env["topic"] == "trigger-events"
    assert env["payload"]["rule_name"] == "VOLUME_SPIKE"
