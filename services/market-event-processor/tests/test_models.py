import json

import pytest

from market_event_processor.models import (
    RawMarketEvent,
    build_enriched_envelope,
    parse_raw_pubsub_message,
    timestamp_ms_from_ns,
)


def test_parse_raw_envelope():
    envelope = {
        "message_id": "raw-1",
        "source_container": "polygon-websocket-streamer",
        "topic": "raw-market-events",
        "payload": {
            "symbol": "aapl",
            "event_type": "trade",
            "price": 150.0,
            "volume": 1000.0,
            "timestamp_ns": 1_700_000_000_000_000_000,
            "raw_payload": {"ev": "T"},
        },
    }
    msg_id, raw, full = parse_raw_pubsub_message(json.dumps(envelope).encode())
    assert msg_id == "raw-1"
    assert raw.symbol == "AAPL"
    assert full["topic"] == "raw-market-events"


def test_timestamp_ms_from_ns():
    assert timestamp_ms_from_ns(1_700_000_000_000_000_000) == 1_700_000_000_000
    assert timestamp_ms_from_ns(1_700_000_000_000) == 1_700_000_000_000
    assert timestamp_ms_from_ns(1_700_000_000) == 1_700_000_000_000


def test_build_enriched_envelope():
    from market_event_processor.models import EnrichedMarketEvent

    event = EnrichedMarketEvent(
        symbol="TSLA",
        event_type="trade",
        price=200.0,
        volume=50.0,
        timestamp_ns=1,
        raw_payload={},
        pct_change_5m=2.5,
    )
    env = build_enriched_envelope(event, topic="enriched-market-events")
    assert env["source_container"] == "market-event-processor"
    assert env["payload"]["pct_change_5m"] == 2.5


def test_parse_rejects_invalid():
    with pytest.raises(ValueError):
        parse_raw_pubsub_message(b"not-json")
