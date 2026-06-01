"""RawDecision schema and JSON parsing."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any

from agentic_ai.models import ACTION_ALERT, ACTION_ESCALATE, ACTION_IGNORE

logger = logging.getLogger(__name__)

VALID_ACTIONS = frozenset({ACTION_ALERT, ACTION_ESCALATE, ACTION_IGNORE})

PARSE_FAILURE_REASON = "LLM response parsing failed"
UNAVAILABLE_REASON = "LLM unavailable"


@dataclass(frozen=True)
class RawDecision:
    confidence: float
    reason: str
    action_candidate: str
    event_id: str = ""
    symbol: str = ""
    signal: str = ""
    llm_provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    return data


def parse_raw_decision_response(
    text: str,
    *,
    event_id: str = "",
    symbol: str = "",
    signal: str = "",
    provider: str = "",
) -> RawDecision:
    """Parse LLM JSON into RawDecision; raises ValueError on invalid structure."""
    data = _extract_json_object(text)
    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    reason = str(data.get("reason") or "").strip()
    action = str(data.get("action_candidate") or ACTION_IGNORE).upper()
    if action not in VALID_ACTIONS:
        raise ValueError(f"invalid action_candidate: {action}")
    if not reason:
        raise ValueError("reason is required")
    return RawDecision(
        confidence=confidence,
        reason=reason,
        action_candidate=action,
        event_id=event_id,
        symbol=symbol,
        signal=signal,
        llm_provider=provider,
    )


def default_raw_decision(
    *,
    event_id: str,
    symbol: str,
    signal: str,
    reason: str,
    provider: str = "",
) -> RawDecision:
    return RawDecision(
        confidence=0.0,
        reason=reason,
        action_candidate=ACTION_IGNORE,
        event_id=event_id,
        symbol=symbol,
        signal=signal,
        llm_provider=provider,
    )
