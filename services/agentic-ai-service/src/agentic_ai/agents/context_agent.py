"""ContextAgent — news headlines with graceful fallback."""

from __future__ import annotations

import logging

from agentic_ai.agents.common import trigger_from_state
from agentic_ai.agents.news_client import MAX_HEADLINES, NewsClient, get_news_client
from agentic_ai.state import WorkflowState

logger = logging.getLogger(__name__)


def _unavailable_summary(*, error: str | None = None) -> dict:
    summary: dict = {"available": False, "headlines": []}
    if error:
        summary["error"] = error
    return summary


def _available_summary(headlines: list[dict]) -> dict:
    titles = [h.get("title", "") for h in headlines if h.get("title")]
    text_summary = "; ".join(titles[:3]) if titles else "recent headlines fetched"
    return {
        "available": True,
        "headlines": headlines,
        "summary": text_summary,
    }


def fetch_context_for_symbol(
    symbol: str,
    *,
    client: NewsClient | None = None,
    limit: int = MAX_HEADLINES,
) -> dict:
    news = client or get_news_client()
    try:
        headlines = news.fetch_headlines(symbol, limit=limit)
        return _available_summary(headlines)
    except Exception as exc:
        logger.warning("ContextAgent news fetch failed symbol=%s: %s", symbol, exc)
        return _unavailable_summary(error=str(exc))


def context_agent_node(state: WorkflowState) -> WorkflowState:
    trigger = trigger_from_state(state)
    context_summary = fetch_context_for_symbol(trigger.symbol)
    return {"context_summary": context_summary}
