"""ControlAgent — cooldown, confidence gate, escalation, final AlertDecision."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agentic_ai.agents.common import market_snapshot_from_state, trigger_from_state
from agentic_ai.governance.cooldown import get_cooldown_store
from agentic_ai.governance.thresholds import GovernanceThresholds, load_governance_thresholds
from agentic_ai.models import (
    ACTION_ALERT,
    ACTION_ESCALATE,
    ACTION_IGNORE,
    AlertDecision,
    TriggerEvent,
)
from agentic_ai.state import WorkflowState

logger = logging.getLogger(__name__)

_default_thresholds: GovernanceThresholds | None = None


def get_governance_thresholds() -> GovernanceThresholds:
    global _default_thresholds
    if _default_thresholds is None:
        _default_thresholds = load_governance_thresholds()
    return _default_thresholds


def set_governance_thresholds(thresholds: GovernanceThresholds | None) -> None:
    global _default_thresholds
    _default_thresholds = thresholds


def _context_summary_text(context: dict[str, Any] | None) -> str:
    if not context or not isinstance(context, dict):
        return ""
    if not context.get("available"):
        note = "No news context was available."
        summary = str(context.get("summary") or "").strip()
        return f"{note} {summary}".strip()
    return str(context.get("summary") or "").strip()


def apply_governance(
    *,
    trigger: TriggerEvent,
    raw: dict[str, Any],
    context_summary: dict[str, Any] | None,
    thresholds: GovernanceThresholds,
    cooldown_store=None,
) -> AlertDecision:
    store = cooldown_store or get_cooldown_store()
    confidence = float(raw.get("confidence", 0.0))
    reason = str(raw.get("reason") or "").strip()
    candidate = str(raw.get("action_candidate") or ACTION_IGNORE).upper()
    ctx_text = _context_summary_text(context_summary)

    if confidence < thresholds.confidence_threshold:
        logger.info(
            "ControlAgent suppress event_id=%s: confidence %.2f < %.2f",
            trigger.event_id,
            confidence,
            thresholds.confidence_threshold,
        )
        return AlertDecision(
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            confidence=confidence,
            reason=reason or f"Suppressed: confidence below {thresholds.confidence_threshold:.0%}",
            action=ACTION_IGNORE,
            context_summary=ctx_text,
            decided_at=datetime.now(timezone.utc).isoformat(),
            measured_magnitude=trigger.triggered_value,
        )

    if store.is_in_cooldown(
        trigger.symbol,
        trigger.rule_name,
        window_minutes=thresholds.cooldown_minutes,
    ):
        logger.info(
            "ControlAgent suppress event_id=%s: cooldown active symbol=%s rule=%s",
            trigger.event_id,
            trigger.symbol,
            trigger.rule_name,
        )
        suppress_reason = (
            f"Suppressed: cooldown window ({thresholds.cooldown_minutes:.0f} min) active"
        )
        if reason:
            suppress_reason = f"{reason} ({suppress_reason})"
        return AlertDecision(
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            confidence=confidence,
            reason=suppress_reason,
            action=ACTION_IGNORE,
            context_summary=ctx_text,
            decided_at=datetime.now(timezone.utc).isoformat(),
            measured_magnitude=trigger.triggered_value,
        )

    if confidence >= thresholds.escalation_threshold:
        action = ACTION_ESCALATE
    elif candidate in (ACTION_ALERT, ACTION_ESCALATE):
        action = ACTION_ALERT if candidate == ACTION_ALERT else ACTION_ESCALATE
    else:
        action = ACTION_IGNORE

    if action == ACTION_IGNORE:
        logger.info(
            "ControlAgent IGNORE event_id=%s candidate=%s confidence=%.2f",
            trigger.event_id,
            candidate,
            confidence,
        )
        return AlertDecision(
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            confidence=confidence,
            reason=reason or "Suppressed: decision candidate IGNORE",
            action=ACTION_IGNORE,
            context_summary=ctx_text,
            decided_at=datetime.now(timezone.utc).isoformat(),
            measured_magnitude=trigger.triggered_value,
        )

    store.record_alert(
        trigger.symbol,
        trigger.rule_name,
        window_minutes=thresholds.cooldown_minutes,
    )
    logger.info(
        "ControlAgent approved event_id=%s action=%s confidence=%.2f",
        trigger.event_id,
        action,
        confidence,
    )
    return AlertDecision(
        event_id=trigger.event_id,
        symbol=trigger.symbol,
        signal=trigger.rule_name,
        confidence=confidence,
        reason=reason,
        action=action,
        context_summary=ctx_text,
        decided_at=datetime.now(timezone.utc).isoformat(),
        measured_magnitude=trigger.triggered_value,
    )


def run_control_agent(state: WorkflowState) -> dict:
    trigger = trigger_from_state(state)
    raw = state.get("raw_decision") or {}
    context = state.get("context_summary")
    if not isinstance(context, dict):
        context = None
    decision = apply_governance(
        trigger=trigger,
        raw=raw,
        context_summary=context,
        thresholds=get_governance_thresholds(),
    )
    return decision.to_dict()


def control_agent_node(state: WorkflowState) -> WorkflowState:
    return {"final_decision": run_control_agent(state)}
