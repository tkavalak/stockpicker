"""LangGraph workflow state (WorkflowState TypedDict)."""

from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    """Mutable state passed through all agent nodes."""

    trigger: dict[str, Any]
    market_snapshot: dict[str, Any] | None
    signal_summary: dict[str, Any] | None
    context_summary: dict[str, Any] | None
    raw_decision: dict[str, Any] | None
    final_decision: dict[str, Any] | None
    abort: bool
