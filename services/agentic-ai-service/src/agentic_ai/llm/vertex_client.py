"""Vertex AI Gemini client (primary LLM)."""

from __future__ import annotations

import logging
import os
from typing import Protocol

logger = logging.getLogger(__name__)

TRANSIENT_EXCEPTION_NAMES = frozenset(
    {
        "ServiceUnavailable",
        "DeadlineExceeded",
        "InternalServerError",
        "ResourceExhausted",
        "Aborted",
    }
)


class LLMCompletionClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        ...


def _is_transient(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in TRANSIENT_EXCEPTION_NAMES:
        return True
    cause = exc.__cause__
    return cause is not None and _is_transient(cause)


class VertexGeminiClient:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        location: str | None = None,
        model_name: str | None = None,
    ) -> None:
        self._project_id = project_id or os.environ.get("GCP_PROJECT_ID", "")
        self._location = location or os.environ.get(
            "VERTEX_AI_LOCATION", os.environ.get("GCP_REGION", "us-central1")
        )
        self._model_name = model_name or os.environ.get("VERTEX_AI_MODEL", "gemini-1.5-flash")
        self._initialized = False

    @property
    def available(self) -> bool:
        return bool(self._project_id)

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        import vertexai

        vertexai.init(project=self._project_id, location=self._location)
        self._initialized = True

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.available:
            raise RuntimeError("Vertex AI not configured (GCP_PROJECT_ID missing)")

        from vertexai.generative_models import GenerationConfig, GenerativeModel

        self._ensure_init()
        model = GenerativeModel(self._model_name)
        config = GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
        prompt = f"{system_prompt}\n\n{user_prompt}"
        response = model.generate_content(prompt, generation_config=config)
        text = getattr(response, "text", None) or ""
        if not text.strip():
            raise RuntimeError("Vertex AI returned empty response")
        return text.strip()

    def complete_with_retry(self, *, system_prompt: str, user_prompt: str) -> str:
        last_exc: BaseException | None = None
        for attempt in range(2):
            try:
                return self.complete(system_prompt=system_prompt, user_prompt=user_prompt)
            except Exception as exc:
                last_exc = exc
                if attempt == 0 and _is_transient(exc):
                    logger.warning("Vertex AI transient error, retrying: %s", exc)
                    continue
                raise
        assert last_exc is not None
        raise last_exc
