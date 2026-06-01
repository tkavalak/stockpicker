"""Firestore cooldown records per symbol + rule type."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

logger = logging.getLogger(__name__)


def cooldown_document_id(symbol: str, rule_name: str) -> str:
    return f"{symbol.upper()}_{rule_name.upper()}"


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).astimezone(timezone.utc)
        except ValueError:
            return None
    return None


class CooldownStore:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        collection: str | None = None,
        client: firestore.Client | None = None,
        default_window_minutes: float = 10.0,
    ) -> None:
        self._client = client or firestore.Client(project=project_id)
        self._collection = collection or os.environ.get(
            "FIRESTORE_COLLECTION_AGENT_STATE", "agent_state"
        )
        self._default_window_minutes = default_window_minutes

    def _doc_ref(self, symbol: str, rule_name: str) -> firestore.DocumentReference:
        doc_id = cooldown_document_id(symbol, rule_name)
        return self._client.collection(self._collection).document(doc_id)

    def get_last_alerted_at(self, symbol: str, rule_name: str) -> datetime | None:
        doc = self._doc_ref(symbol, rule_name).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return _parse_timestamp(data.get("last_alerted_at"))

    def is_in_cooldown(
        self,
        symbol: str,
        rule_name: str,
        *,
        window_minutes: float | None = None,
        now: datetime | None = None,
    ) -> bool:
        last = self.get_last_alerted_at(symbol, rule_name)
        if last is None:
            return False
        window = window_minutes if window_minutes is not None else self._default_window_minutes
        current = now or datetime.now(timezone.utc)
        return (current - last) < timedelta(minutes=window)

    def record_alert(
        self,
        symbol: str,
        rule_name: str,
        *,
        window_minutes: float | None = None,
        alerted_at: datetime | None = None,
    ) -> None:
        when = alerted_at or datetime.now(timezone.utc)
        window = window_minutes if window_minutes is not None else self._default_window_minutes
        self._doc_ref(symbol, rule_name).set(
            {
                "symbol": symbol.upper(),
                "rule_name": rule_name.upper(),
                "window_minutes": window,
                "last_alerted_at": when.isoformat(),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.debug(
            "Cooldown recorded %s/%s at %s",
            symbol,
            rule_name,
            when.isoformat(),
        )


_default_store: CooldownStore | None = None


def get_cooldown_store() -> CooldownStore:
    global _default_store
    if _default_store is None:
        _default_store = CooldownStore()
    return _default_store


def set_cooldown_store(store: CooldownStore | None) -> None:
    global _default_store
    _default_store = store
