"""Channel types, routing rules, and status constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CHANNEL_SLACK = "slack"
CHANNEL_EMAIL = "email"
CHANNEL_TEAMS = "teams"
CHANNEL_TWILIO = "twilio"
CHANNEL_PUSHOVER = "pushover"

ALL_CHANNEL_TYPES = frozenset(
    {
        CHANNEL_SLACK,
        CHANNEL_EMAIL,
        CHANNEL_TEAMS,
        CHANNEL_TWILIO,
        CHANNEL_PUSHOVER,
    }
)

STATUS_CONNECTED = "connected"
STATUS_ERROR = "error"
STATUS_DISCONNECTED = "disconnected"

CONSECUTIVE_FAILURE_LIMIT = 3


@dataclass(frozen=True)
class RoutingRule:
    """Filter alerts by symbol and/or action. Empty lists mean no filter (all)."""

    symbols: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()

    def matches(self, *, symbol: str, action: str) -> bool:
        if self.symbols:
            normalized = {s.upper() for s in self.symbols}
            if "*" not in normalized and symbol.upper() not in normalized:
                return False
        if self.actions:
            if action.upper() not in {a.upper() for a in self.actions}:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
            "actions": list(self.actions),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RoutingRule | None:
        if not data:
            return None
        symbols = data.get("symbols") or []
        actions = data.get("actions") or []
        if not symbols and not actions:
            return None
        if isinstance(symbols, str):
            symbols = [symbols]
        if isinstance(actions, str):
            actions = [actions]
        return cls(
            symbols=tuple(str(s).upper() for s in symbols),
            actions=tuple(str(a).upper() for a in actions),
        )


@dataclass
class ChannelRecord:
    channel_type: str
    status: str
    enabled: bool
    consecutive_failures: int
    last_verified_at: str | None
    routing_rule: RoutingRule | None
    credentials: dict[str, Any] = field(default_factory=dict)

    def is_deliverable(self) -> bool:
        return self.enabled and self.status == STATUS_CONNECTED

    def to_public_dict(self) -> dict[str, Any]:
        """API response without secret credentials."""
        return {
            "type": self.channel_type,
            "status": self.status,
            "enabled": self.enabled,
            "consecutive_failures": self.consecutive_failures,
            "last_verified_at": self.last_verified_at,
            "routing_rule": self.routing_rule.to_dict() if self.routing_rule else None,
            "has_credentials": bool(self.credentials),
        }

    def to_firestore_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "enabled": self.enabled,
            "consecutive_failures": self.consecutive_failures,
            "last_verified_at": self.last_verified_at,
            "routing_rule": self.routing_rule.to_dict() if self.routing_rule else None,
            "credentials": self.credentials,
        }

    @classmethod
    def from_firestore_dict(
        cls, channel_type: str, data: dict[str, Any] | None
    ) -> ChannelRecord:
        data = data or {}
        return cls(
            channel_type=channel_type,
            status=str(data.get("status") or STATUS_DISCONNECTED),
            enabled=bool(data.get("enabled", False)),
            consecutive_failures=int(data.get("consecutive_failures") or 0),
            last_verified_at=data.get("last_verified_at"),
            routing_rule=RoutingRule.from_dict(data.get("routing_rule")),
            credentials=dict(data.get("credentials") or {}),
        )
