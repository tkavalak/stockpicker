"""Route LLM requests: Vertex AI primary, OpenAI fallback."""

from __future__ import annotations

import logging

from agentic_ai.llm.openai_client import OpenAIChatClient
from agentic_ai.llm.vertex_client import VertexGeminiClient

logger = logging.getLogger(__name__)


class LLMRouter:
    def __init__(
        self,
        *,
        vertex: VertexGeminiClient | None = None,
        openai: OpenAIChatClient | None = None,
    ) -> None:
        self._vertex = vertex or VertexGeminiClient()
        self._openai = openai or OpenAIChatClient()

    def complete(self, *, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """
        Returns (response_text, provider_name).
        Raises RuntimeError if all providers fail.
        """
        vertex_error: str | None = None
        if self._vertex.available:
            try:
                text = self._vertex.complete_with_retry(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
                return text, "vertex_ai"
            except Exception as exc:
                vertex_error = str(exc)
                logger.warning("Vertex AI failed, trying OpenAI fallback: %s", exc)

        if self._openai.available:
            try:
                text = self._openai.complete(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
                return text, "openai"
            except Exception as exc:
                logger.error("OpenAI fallback failed: %s", exc)
                raise RuntimeError(
                    f"LLM providers unavailable (vertex={vertex_error}, openai={exc})"
                ) from exc

        raise RuntimeError(
            f"LLM providers not configured (vertex={vertex_error or 'n/a'})"
        )


_default_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter()
    return _default_router


def set_llm_router(router: LLMRouter | None) -> None:
    global _default_router
    _default_router = router
