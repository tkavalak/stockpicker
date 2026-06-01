"""Fetch recent news headlines for a symbol (Polygon-compatible API)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

logger = logging.getLogger(__name__)

DEFAULT_NEWS_API_URL = "https://api.polygon.io/v2/reference/news"
MAX_HEADLINES = 5


class NewsClient(Protocol):
    def fetch_headlines(self, symbol: str, *, limit: int = MAX_HEADLINES) -> list[dict[str, Any]]:
        ...


def _publisher_name(item: dict[str, Any]) -> str:
    publisher = item.get("publisher")
    if isinstance(publisher, dict):
        return str(publisher.get("name") or "")
    return str(item.get("source") or "")


def _normalize_headline(item: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(item.get("title") or ""),
        "published_at": str(
            item.get("published_utc")
            or item.get("published_at")
            or item.get("published")
            or ""
        ),
        "url": str(item.get("article_url") or item.get("url") or ""),
        "source": _publisher_name(item),
    }


class HttpNewsClient:
    """HTTP client for Polygon-style GET /v2/reference/news?ticker=SYMBOL."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_sec: float = 10.0,
    ) -> None:
        self._base_url = (base_url or os.environ.get("NEWS_API_URL") or DEFAULT_NEWS_API_URL).rstrip("/")
        self._api_key = api_key or os.environ.get("POLYGON_API_KEY", "")
        self._timeout_sec = timeout_sec

    def fetch_headlines(self, symbol: str, *, limit: int = MAX_HEADLINES) -> list[dict[str, Any]]:
        if not self._api_key:
            raise ValueError("POLYGON_API_KEY not configured")

        params = {
            "ticker": symbol.upper(),
            "limit": str(min(limit, MAX_HEADLINES)),
            "apiKey": self._api_key,
        }
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ConnectionError(str(exc)) from exc

        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("news API response must be a JSON object")

        results = data.get("results")
        if not isinstance(results, list):
            return []

        headlines: list[dict[str, Any]] = []
        for item in results[:limit]:
            if isinstance(item, dict) and item.get("title"):
                headlines.append(_normalize_headline(item))
        return headlines


_default_client: HttpNewsClient | None = None


def get_news_client() -> HttpNewsClient:
    global _default_client
    if _default_client is None:
        _default_client = HttpNewsClient()
    return _default_client


def set_news_client(client: HttpNewsClient | None) -> None:
    global _default_client
    _default_client = client
