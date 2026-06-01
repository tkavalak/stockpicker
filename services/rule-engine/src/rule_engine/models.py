"""EnrichedMarketEvent, TriggerEvent, and RuleConfig schemas."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

SOURCE_CONTAINER = "rule-engine-service"
SCHEMA_VERSION = "1.0"

DEFAULT_THRESHOLDS = {
    "PRICE_SPIKE_5M": 0.5,
}


@dataclass(frozen=True)
class RuleConfig:
    rule_name: str
    enabled: bool
    threshold: float
    symbols: list[str]

    @classmethod
    def from_firestore(cls, data: dict[str, Any]) -> RuleConfig:
        symbols = data.get("symbols") or ["*"]
        if isinstance(symbols, str):
            symbols = [symbols]
        return cls(
            rule_name=str(data["rule_name"]),
            enabled=bool(data.get("enabled", True)),
            threshold=float(data["threshold"]),
            symbols=[str(s).upper() for s in symbols],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "enabled": self.enabled,
            "threshold": self.threshold,
            "symbols": self.symbols,
        }


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichedMarketEvent:
        return cls(
            symbol=str(data["symbol"]).upper(),
            event_type=str(data["event_type"]),
            price=float(data["price"]),
            volume=float(data.get("volume") or 0),
            timestamp_ns=int(data["timestamp_ns"]),
            raw_payload=dict(data.get("raw_payload") or {}),
            pct_change_1m=_optional_float(data.get("pct_change_1m")),
            pct_change_5m=_optional_float(data.get("pct_change_5m")),
            avg_volume_20=_optional_float(data.get("avg_volume_20")),
            volume_ratio=_optional_float(data.get("volume_ratio")),
            volatility_score=_optional_float(data.get("volatility_score")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True)
class RuleFire:
    rule_name: str
    triggered_value: float
    threshold_value: float


@dataclass(frozen=True)
class TriggerEvent:
    event_id: str
    symbol: str
    rule_name: str
    triggered_value: float
    threshold_value: float
    enriched_event: dict[str, Any]
    fired_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def symbol_matches(symbol: str, allowed: list[str]) -> bool:
    if "*" in allowed:
        return True
    return symbol.upper() in allowed


def parse_enriched_pubsub_message(data: bytes) -> tuple[str, EnrichedMarketEvent, dict[str, Any]]:
    """Parse Pub/Sub bytes into (upstream_message_id, event, full_envelope)."""
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

    return message_id, EnrichedMarketEvent.from_dict(payload), envelope


def build_trigger_envelope(trigger: TriggerEvent, *, topic: str) -> dict[str, Any]:
    return {
        "message_id": str(uuid.uuid4()),
        "source_container": SOURCE_CONTAINER,
        "topic": topic,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "payload": trigger.to_dict(),
    }


def envelope_to_json_bytes(envelope: dict[str, Any]) -> bytes:
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")
