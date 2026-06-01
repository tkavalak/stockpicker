from unittest.mock import MagicMock

import pytest

from agentic_ai.llm.openai_client import OpenAIChatClient
from agentic_ai.llm.router import LLMRouter
from agentic_ai.llm.vertex_client import VertexGeminiClient


def test_vertex_primary_success():
    vertex = MagicMock(spec=VertexGeminiClient)
    vertex.available = True
    vertex.complete_with_retry.return_value = '{"confidence": 0.8, "reason": "ok", "action_candidate": "ALERT"}'
    openai = MagicMock(spec=OpenAIChatClient)
    openai.available = True

    text, provider = LLMRouter(vertex=vertex, openai=openai).complete(
        system_prompt="sys", user_prompt="user"
    )
    assert provider == "vertex_ai"
    assert "ALERT" in text
    openai.complete.assert_not_called()


def test_openai_fallback_when_vertex_fails():
    vertex = MagicMock(spec=VertexGeminiClient)
    vertex.available = True
    vertex.complete_with_retry.side_effect = RuntimeError("vertex down")
    openai = MagicMock(spec=OpenAIChatClient)
    openai.available = True
    openai.complete.return_value = '{"confidence": 0.7, "reason": "fb", "action_candidate": "ALERT"}'

    text, provider = LLMRouter(vertex=vertex, openai=openai).complete(
        system_prompt="sys", user_prompt="user"
    )
    assert provider == "openai"
    openai.complete.assert_called_once()


def test_no_providers_raises():
    vertex = MagicMock(spec=VertexGeminiClient)
    vertex.available = False
    openai = MagicMock(spec=OpenAIChatClient)
    openai.available = False
    with pytest.raises(RuntimeError, match="not configured"):
        LLMRouter(vertex=vertex, openai=openai).complete(
            system_prompt="s", user_prompt="u"
        )
