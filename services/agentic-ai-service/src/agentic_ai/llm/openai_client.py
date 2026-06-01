"""OpenAI GPT-4o client (fallback LLM)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class OpenAIChatClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        if not self.available:
            raise RuntimeError("OpenAI not configured (OPENAI_API_KEY missing)")

        from openai import OpenAI

        client = OpenAI(api_key=self._api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        choice = response.choices[0].message.content
        if not choice or not choice.strip():
            raise RuntimeError("OpenAI returned empty response")
        return choice.strip()
