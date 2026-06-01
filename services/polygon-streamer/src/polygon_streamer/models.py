"""MarketEventMessage schema and Polygon message conversion."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from polygon.websocket.models import EquityAgg, EquityTrade, WebSocketMessage

SOURCE_CONTAINER = "polygon-websocket-streamer"
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class MarketEventMessage:
    symbol: str
    event_type: str
    price: float
    volume: float
    timestamp_ns: int
    raw_payload: dict[str, Any]


def normalize_timestamp_ns(timestamp: int) -> int:
    if timestamp > 1_000_000_000_000_000_000:
        return timestamp
    if timestamp > 1_000_000_000_000_000:
        return timestamp * 1_000
    if timestamp > 1_000_000_000_000:
        return timestamp * 1_000_000
    return timestamp * 1_000_000_000


def polygon_message_to_raw(msg: WebSocketMessage) -> dict[str, Any] | None:
    if isinstance(msg, EquityTrade):
        return {
            "ev": msg.event_type,
            "sym": msg.symbol,
            "p": msg.price,
            "s": msg.size,
            "t": msg.timestamp,
        }
    if isinstance(msg, EquityAgg):
        return {
            "ev": msg.event_type,
            "sym": msg.symbol,
            "c": msg.close,
            "v": msg.volume,
            "e": msg.end_timestamp,
        }
    return None


def to_market_event_message(msg: WebSocketMessage) -> MarketEventMessage | None:
    if isinstance(msg, EquityTrade):
        if msg.symbol is None or msg.price is None or msg.timestamp is None:
            return None
        raw = polygon_message_to_raw(msg) or {}
        return MarketEventMessage(
            symbol=str(msg.symbol).upper(),
            event_type="trade",
            price=float(msg.price),
            volume=float(msg.size or 0),
            timestamp_ns=normalize_timestamp_ns(int(msg.timestamp)),
            raw_payload=raw,
        )
    if isinstance(msg, EquityAgg):
        if msg.symbol is None or msg.close is None or msg.end_timestamp is None:
            return None
        raw = polygon_message_to_raw(msg) or {}
        return MarketEventMessage(
            symbol=str(msg.symbol).upper(),
            event_type="aggregate",
            price=float(msg.close),
            volume=float(msg.volume or 0),
            timestamp_ns=normalize_timestamp_ns(int(msg.end_timestamp)),
            raw_payload=raw,
        )
    return None


def build_pubsub_envelope(
    event: MarketEventMessage,
    *,
    topic: str,
    message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "message_id": message_id or str(uuid.uuid4()),
        "source_container": SOURCE_CONTAINER,
        "topic": topic,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "payload": asdict(event),
    }


def envelope_to_json_bytes(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")
