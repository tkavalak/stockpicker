"""Load rule_configs from Firestore with a 30-second TTL cache."""

from __future__ import annotations

import logging
import time
from typing import Any

from google.cloud import firestore

from rule_engine.models import DEFAULT_THRESHOLDS, RuleConfig

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 30.0


class RuleConfigLoader:
    def __init__(
        self,
        *,
        project_id: str | None = None,
        collection: str = "rule_configs",
        client: firestore.Client | None = None,
        cache_ttl_sec: float = CACHE_TTL_SEC,
    ) -> None:
        self._client = client or firestore.Client(project=project_id)
        self._collection = collection
        self._cache_ttl_sec = cache_ttl_sec
        self._configs: dict[str, RuleConfig] = {}
        self._loaded_at: float = 0.0

    @property
    def cache_age_seconds(self) -> float:
        if self._loaded_at == 0:
            return float("inf")
        return time.monotonic() - self._loaded_at

    def get_configs(self, *, force_reload: bool = False) -> dict[str, RuleConfig]:
        if force_reload or self.cache_age_seconds >= self._cache_ttl_sec:
            self._reload()
        return dict(self._configs)

    def _reload(self) -> None:
        configs: dict[str, RuleConfig] = {}
        for doc in self._client.collection(self._collection).stream():
            data = doc.to_dict() or {}
            if "rule_name" not in data:
                data["rule_name"] = doc.id
            try:
                configs[doc.id] = RuleConfig.from_firestore(data)
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid rule_configs/%s: %s", doc.id, exc)

        for rule_name, default_threshold in DEFAULT_THRESHOLDS.items():
            if rule_name not in configs:
                configs[rule_name] = RuleConfig(
                    rule_name=rule_name,
                    enabled=True,
                    threshold=default_threshold,
                    symbols=["*"],
                )

        self._configs = configs
        self._loaded_at = time.monotonic()
        logger.info("Loaded %d rule configs from Firestore", len(self._configs))

    def configs_for_admin(self) -> list[dict[str, Any]]:
        return [cfg.to_dict() for cfg in self.get_configs().values()]
