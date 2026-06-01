from unittest.mock import MagicMock

from agentic_ai.agents.context_agent import context_agent_node, fetch_context_for_symbol
from agentic_ai.agents.news_client import set_news_client
from agentic_ai.models import TriggerEvent


def test_fetch_success():
    mock = MagicMock()
    mock.fetch_headlines.return_value = [
        {"title": "Earnings beat", "published_at": "t1", "url": "http://x", "source": "Reuters"}
    ]
    summary = fetch_context_for_symbol("AAPL", client=mock)
    assert summary["available"] is True
    assert len(summary["headlines"]) == 1
    mock.fetch_headlines.assert_called_once()


def test_fetch_failure_continues():
    mock = MagicMock()
    mock.fetch_headlines.side_effect = ConnectionError("timeout")
    summary = fetch_context_for_symbol("AAPL", client=mock)
    assert summary["available"] is False
    assert summary["headlines"] == []


def test_context_agent_node():
    mock = MagicMock()
    mock.fetch_headlines.return_value = []
    set_news_client(mock)
    try:
        state = {
            "trigger": TriggerEvent(
                event_id="e1",
                symbol="TSLA",
                rule_name="PRICE_SPIKE_5M",
                triggered_value=2.0,
                threshold_value=2.0,
                enriched_event={},
                fired_at="2026-01-01T00:00:00+00:00",
            ).to_dict()
        }
        out = context_agent_node(state)
        assert out["context_summary"]["available"] is True
        mock.fetch_headlines.assert_called_with("TSLA", limit=5)
    finally:
        set_news_client(None)
