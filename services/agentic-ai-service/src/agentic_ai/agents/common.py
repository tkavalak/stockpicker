"""Shared helpers for LangGraph agent nodes."""

from __future__ import annotations

from datetime import datetime, timezone

from agentic_ai.models import TriggerEvent
from agentic_ai.state import WorkflowState


def parse_fired_at(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        normalized = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def trigger_from_state(state: WorkflowState) -> TriggerEvent:
    raw = state.get("trigger") or {}
    return TriggerEvent.from_dict(raw)


def market_snapshot_from_state(state: WorkflowState) -> dict:
    snapshot = state.get("market_snapshot")
    if isinstance(snapshot, dict):
        return snapshot
    return {}
