"""DataAgent — validate TriggerEvent and build market_snapshot."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from agentic_ai.agents.common import parse_fired_at, trigger_from_state
from agentic_ai.models import ignore_decision
from agentic_ai.state import WorkflowState

logger = logging.getLogger(__name__)

STALE_TRIGGER_SEC = float(os.environ.get("STALE_TRIGGER_SEC", "10"))

VALID_RULE_NAMES = frozenset({"PRICE_SPIKE_5M", "VOLUME_SPIKE"})


def _abort(trigger, *, reason: str) -> WorkflowState:
    decision = ignore_decision(trigger, reason=reason)
    return {
        "abort": True,
        "final_decision": decision.to_dict(),
        "market_snapshot": None,
    }


def _build_market_snapshot(trigger) -> dict[str, Any]:
    payload = trigger.enriched_event.get("payload")
    if isinstance(payload, dict):
        snapshot: dict[str, Any] = dict(payload)
    else:
        snapshot = dict(trigger.enriched_event)

    snapshot["symbol"] = str(snapshot.get("symbol") or trigger.symbol).upper()
    snapshot["rule_name"] = str(snapshot.get("rule_name") or trigger.rule_name)
    snapshot["triggered_value"] = float(
        snapshot.get("triggered_value", trigger.triggered_value)
    )
    snapshot["threshold_value"] = float(
        snapshot.get("threshold_value", trigger.threshold_value)
    )
    return snapshot


def data_agent_node(state: WorkflowState) -> WorkflowState:
    trigger = trigger_from_state(state)

    symbol = (trigger.symbol or "").strip()
    if not symbol:
        logger.info("DataAgent abort: missing symbol event_id=%s", trigger.event_id)
        return _abort(trigger, reason="invalid trigger: missing symbol")

    rule_name = (trigger.rule_name or "").strip().upper()
    if rule_name not in VALID_RULE_NAMES:
        logger.info(
            "DataAgent abort: invalid rule_name=%s event_id=%s",
            trigger.rule_name,
            trigger.event_id,
        )
        return _abort(trigger, reason=f"invalid trigger: unknown rule {trigger.rule_name}")

    fired = parse_fired_at(trigger.fired_at)
    now = datetime.now(timezone.utc)
    if fired is not None:
        age_sec = (now - fired.astimezone(timezone.utc)).total_seconds()
        if age_sec > STALE_TRIGGER_SEC:
            logger.info(
                "DataAgent abort: stale trigger event_id=%s age_sec=%.1f",
                trigger.event_id,
                age_sec,
            )
            return _abort(trigger, reason="stale trigger event")

    snapshot = _build_market_snapshot(trigger)
    return {
        "market_snapshot": snapshot,
        "abort": False,
    }
