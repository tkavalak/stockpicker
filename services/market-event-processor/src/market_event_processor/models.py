"""Raw and enriched market event models and Pub/Sub envelopes."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

SOURCE_CONTAINER = "market-event-processor"
SCHEMA_VERSION = "1.0"

ONE_MINUTE_MS = 60 * 1000
FIVE_MINUTES_MS = 5 * 60 * 1000
PRICE_HISTORY_RETENTION_MS = FIVE_MINUTES_MS + 60_000


@dataclass(frozen=True)
class RawMarketEvent:
    symbol: str
    event_type: str
    price: float
    volume: float
    timestamp_ns: int
    raw_payload: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RawMarketEvent:
        return cls(
            symbol=str(data["symbol"]).upper(),
            event_type=str(data["event_type"]),
            price=float(data["price"]),
            volume=float(data.get("volume") or 0),
            timestamp_ns=int(data["timestamp_ns"]),
            raw_payload=dict(data.get("raw_payload") or {}),
        )


@dataclass(frozen=True)
class EnrichedMarketEvent:
    symbol: str
    event_type: str
    price: float
    volume: float
    timestamp_ns: int
    raw_payload: dict[str, Any]
    pct_change_1m: float | None = None
    pct_change_5m: float | None = None
    avg_volume_20: float | None = None
    volume_ratio: float | None = None
    volatility_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def timestamp_ms_from_ns(timestamp_ns: int) -> int:
    """Normalize Polygon ns/ms/s timestamps to milliseconds."""
    if timestamp_ns > 1_000_000_000_000_000:
        return timestamp_ns // 1_000_000
    if timestamp_ns > 1_000_000_000_000:
        return timestamp_ns
    return timestamp_ns * 1000


def parse_raw_pubsub_message(
    data: bytes,
) -> tuple[str, RawMarketEvent, dict[str, Any]]:
    try:
        envelope = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON envelope: {exc}") from exc

    if not isinstance(envelope, dict):
        raise ValueError("envelope must be a JSON object")

    message_id = str(envelope.get("message_id") or uuid.uuid4())
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("envelope missing payload object")

    return message_id, RawMarketEvent.from_dict(payload), envelope


def build_enriched_envelope(
    event: EnrichedMarketEvent,
    *,
    topic: str,
    upstream_message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "message_id": upstream_message_id or str(uuid.uuid4()),
        "source_container": SOURCE_CONTAINER,
        "topic": topic,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "payload": event.to_dict(),
    }


def envelope_to_json_bytes(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")
