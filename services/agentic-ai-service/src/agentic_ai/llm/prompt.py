"""Construct DecisionAgent prompts from WorkflowState."""

from __future__ import annotations

import json
from typing import Any

from agentic_ai.agents.common import market_snapshot_from_state, trigger_from_state
from agentic_ai.state import WorkflowState

SYSTEM_PROMPT = """You are a stock movement validation assistant for an alerting system.
Evaluate whether a rule-engine trigger should become a trader alert.

Respond with JSON only, matching this schema:
{
  "confidence": <float 0.0-1.0>,
  "reason": "<1-3 sentences plain language referencing specific signals>",
  "action_candidate": "ALERT" | "ESCALATE" | "IGNORE"
}

Rules:
- Use ALERT for credible movements worth notifying.
- Use ESCALATE only for exceptional conviction (confidence >= 0.9).
- Use IGNORE when the trigger looks like noise or data is insufficient.
- Reference signal_type, price/volume metrics, trend, momentum, and news when available.
- If news context is unavailable, still provide a reason and note that no news was available.
"""


def _headline_titles(context_summary: dict[str, Any] | None) -> list[str]:
    if not context_summary:
        return []
    headlines = context_summary.get("headlines")
    if not isinstance(headlines, list):
        return []
    titles: list[str] = []
    for item in headlines:
        if isinstance(item, dict) and item.get("title"):
            titles.append(str(item["title"]))
    return titles[:5]


def build_decision_prompt(state: WorkflowState) -> tuple[str, str]:
    """Return (system_prompt, user_prompt)."""
    trigger = trigger_from_state(state)
    snapshot = market_snapshot_from_state(state)
    signal_summary = state.get("signal_summary") or {}
    context_summary = state.get("context_summary") or {}

    context_available = bool(context_summary.get("available"))
    news_headlines = _headline_titles(context_summary if isinstance(context_summary, dict) else None)

    user_payload = {
        "symbol": trigger.symbol,
        "signal_type": trigger.rule_name,
        "triggered_value": trigger.triggered_value,
        "threshold_value": trigger.threshold_value,
        "pct_change_5m": snapshot.get("pct_change_5m"),
        "pct_change_1m": snapshot.get("pct_change_1m"),
        "volume_ratio": snapshot.get("volume_ratio"),
        "volatility_score": snapshot.get("volatility_score"),
        "price": snapshot.get("price"),
        "trend_direction": signal_summary.get("trend"),
        "momentum_score": signal_summary.get("momentum_score"),
        "support_proximity": signal_summary.get("support_proximity"),
        "context_available": context_available,
        "news_headlines": news_headlines,
        "context_summary_text": context_summary.get("summary") if isinstance(context_summary, dict) else None,
    }

    user_prompt = (
        "Analyze this trigger and return JSON only.\n\n"
        f"{json.dumps(user_payload, indent=2)}"
    )
    return SYSTEM_PROMPT, user_prompt
