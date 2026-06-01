import json

from polygon.websocket.models import EquityAgg, EquityTrade

from polygon_streamer.models import (
    MarketEventMessage,
    build_pubsub_envelope,
    envelope_to_json_bytes,
    normalize_timestamp_ns,
    to_market_event_message,
)


def test_normalize_timestamp_ms_to_ns():
    assert normalize_timestamp_ns(1_700_000_000_000) == 1_700_000_000_000_000_000


def test_trade_to_market_event_message():
    trade = EquityTrade(
        "T",
        "AAPL",
        None,
        None,
        None,
        150.25,
        100,
        None,
        1_700_000_000_000,
        None,
        None,
        None,
    )
    event = to_market_event_message(trade)
    assert event is not None
    assert event.symbol == "AAPL"
    assert event.event_type == "trade"
    assert event.price == 150.25
    assert event.volume == 100.0
    assert event.timestamp_ns == 1_700_000_000_000_000_000
    assert event.raw_payload["sym"] == "AAPL"


def test_aggregate_to_market_event_message():
    agg = EquityAgg(
        "A",
        "TSLA",
        5000.0,
        None,
        None,
        None,
        None,
        201.5,
        None,
        None,
        None,
        None,
        1_700_000_000_000,
        1_700_000_001_000,
        None,
    )
    event = to_market_event_message(agg)
    assert event is not None
    assert event.event_type == "aggregate"
    assert event.price == 201.5
    assert event.volume == 5000.0


def test_pubsub_envelope_serialisation():
    event = MarketEventMessage(
        symbol="NVDA",
        event_type="trade",
        price=10.0,
        volume=1.0,
        timestamp_ns=99,
        raw_payload={"sym": "NVDA"},
    )
    envelope = build_pubsub_envelope(event, topic="raw-market-events")
    raw = envelope_to_json_bytes(envelope)
    parsed = json.loads(raw)
    assert parsed["source_container"] == "polygon-websocket-streamer"
    assert parsed["topic"] == "raw-market-events"
    assert parsed["schema_version"] == "1.0"
    assert parsed["payload"]["symbol"] == "NVDA"
    assert "message_id" in parsed
    assert "published_at" in parsed
