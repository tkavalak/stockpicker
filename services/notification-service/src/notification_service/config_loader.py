"""Load notification channels from Firestore (60s TTL)."""

from __future__ import annotations

import logging
import time

from notification_service.channels import ChannelRecord
from notification_service.config_store import NotificationConfigStore

logger = logging.getLogger(__name__)

CACHE_TTL_SEC = 60.0


class NotificationConfigLoader:
    def __init__(
        self,
        *,
        store: NotificationConfigStore | None = None,
        cache_ttl_sec: float = CACHE_TTL_SEC,
    ) -> None:
        self._store = store or NotificationConfigStore()
        self._cache_ttl_sec = cache_ttl_sec
        self._channels: dict[str, ChannelRecord] | None = None
        self._loaded_at: float = 0.0

    @property
    def store(self) -> NotificationConfigStore:
        return self._store

    def get_channels(self, *, force_reload: bool = False) -> dict[str, ChannelRecord]:
        if (
            force_reload
            or self._channels is None
            or time.monotonic() - self._loaded_at >= self._cache_ttl_sec
        ):
            self._channels = self._store.get_channels()
            self._loaded_at = time.monotonic()
            logger.info(
                "Loaded notification channels: %s",
                {k: v.status for k, v in self._channels.items()},
            )
        assert self._channels is not None
        return self._channels

    def invalidate_cache(self) -> None:
        self._channels = None
        self._loaded_at = 0.0
