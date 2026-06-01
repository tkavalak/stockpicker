"""DecisionAgent — LLM synthesis into WorkflowState.raw_decision."""

from __future__ import annotations

import logging
import os

from agentic_ai.agents.common import trigger_from_state
from agentic_ai.llm.prompt import build_decision_prompt
from agentic_ai.llm.raw_decision import (
    PARSE_FAILURE_REASON,
    UNAVAILABLE_REASON,
    default_raw_decision,
    parse_raw_decision_response,
    RawDecision,
)
from agentic_ai.llm.router import get_llm_router
from agentic_ai.models import ACTION_ALERT
from agentic_ai.state import WorkflowState

logger = logging.getLogger(__name__)


def _test_mode_enabled() -> bool:
    return os.environ.get("AGENTIC_TEST_MODE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def run_decision_agent(state: WorkflowState) -> dict:
    """Core logic (testable without LangGraph wrapper)."""
    trigger = trigger_from_state(state)

    if _test_mode_enabled():
        raw = RawDecision(
            confidence=0.85,
            reason="Test mode: auto-alert for rule engine and notification testing",
            action_candidate=ACTION_ALERT,
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            llm_provider="test_mode",
        )
        logger.info(
            "DecisionAgent test_mode event_id=%s action=ALERT confidence=%.2f",
            trigger.event_id,
            raw.confidence,
        )
        return raw.to_dict()

    system_prompt, user_prompt = build_decision_prompt(state)
    router = get_llm_router()

    try:
        response_text, provider = router.complete(
            system_prompt=system_prompt, user_prompt=user_prompt
        )
    except Exception as exc:
        logger.error(
            "DecisionAgent LLM unavailable event_id=%s: %s",
            trigger.event_id,
            exc,
        )
        raw = default_raw_decision(
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            reason=UNAVAILABLE_REASON,
        )
        return raw.to_dict()

    try:
        raw = parse_raw_decision_response(
            response_text,
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            provider=provider,
        )
    except (ValueError, TypeError) as exc:
        logger.warning(
            "DecisionAgent parse failed event_id=%s: %s body=%s",
            trigger.event_id,
            exc,
            response_text[:500],
        )
        raw = default_raw_decision(
            event_id=trigger.event_id,
            symbol=trigger.symbol,
            signal=trigger.rule_name,
            reason=PARSE_FAILURE_REASON,
            provider=provider,
        )

    logger.info(
        "DecisionAgent event_id=%s provider=%s action=%s confidence=%.2f",
        trigger.event_id,
        raw.llm_provider,
        raw.action_candidate,
        raw.confidence,
    )
    return raw.to_dict()


def decision_agent_node(state: WorkflowState) -> WorkflowState:
    return {"raw_decision": run_decision_agent(state)}
