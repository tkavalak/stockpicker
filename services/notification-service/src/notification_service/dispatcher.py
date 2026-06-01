"""Fan-out dispatch with routing rules and consecutive failure handling."""

from __future__ import annotations

import asyncio
import logging

from notification_service.channel_dispatch import ChannelDispatcher
from notification_service.channels import CONSECUTIVE_FAILURE_LIMIT, STATUS_ERROR
from notification_service.config_loader import NotificationConfigLoader
from notification_service.config_store import NotificationConfigStore
from notification_service.models import (
    ACTION_IGNORE,
    AlertDecision,
    DeliveryResult,
    channel_failure_decision,
)
from notification_service.router import NotificationRouter

from notification_service.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(
        self,
        router: NotificationRouter,
        config_loader: NotificationConfigLoader,
        channel_dispatcher: ChannelDispatcher,
        audit: AuditLogger,
        *,
        store: NotificationConfigStore | None = None,
    ) -> None:
        self._router = router
        self._config_loader = config_loader
        self._store = store or config_loader.store
        self._channel_dispatcher = channel_dispatcher
        self._audit = audit

    async def dispatch(self, decision: AlertDecision) -> list[DeliveryResult]:
        if decision.action == ACTION_IGNORE:
            logger.info("Skipping IGNORE decision %s", decision.decision_id)
            return []

        channel_types = self._router.channels_for(decision)
        if not channel_types:
            logger.warning("No channels configured for decision %s", decision.decision_id)
            return []

        channels = self._router.get_channels()
        tasks: list[asyncio.Task[DeliveryResult]] = []
        for channel_type in channel_types:
            record = channels[channel_type]
            tasks.append(
                asyncio.create_task(
                    self._channel_dispatcher.send_to_channel(
                        channel_type, decision, record
                    )
                )
            )

        results: list[DeliveryResult] = []
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        newly_errored: list[tuple[str, str]] = []

        for channel_type, item in zip(channel_types, gathered):
            if isinstance(item, Exception):
                result = DeliveryResult(
                    channel=channel_type,
                    status="failed",
                    http_status=None,
                    latency_ms=0,
                    error=str(item),
                )
            else:
                result = item
            results.append(result)
            self._audit.log_delivery(decision, result)

            updated = self._store.record_delivery_outcome(
                channel_type,
                success=result.status == "delivered",
                error=result.error,
            )
            if (
                updated.status == STATUS_ERROR
                and updated.consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT
            ):
                newly_errored.append((channel_type, result.error or "unknown"))

        if newly_errored:
            await self._notify_channel_failures(newly_errored, channels)

        self._config_loader.invalidate_cache()
        return results

    async def _notify_channel_failures(
        self,
        failures: list[tuple[str, str]],
        channels: dict,
    ) -> None:
        """Alert via remaining working channels when one channel hits error status."""
        for channel_type, error in failures:
            notice = channel_failure_decision(channel_type, error)
            backup_types = [
                ct
                for ct, rec in channels.items()
                if ct != channel_type and rec.is_deliverable()
            ]
            if not backup_types:
                logger.error(
                    "No backup channels to report failure of %s", channel_type
                )
                continue
            for backup in backup_types:
                result = await self._channel_dispatcher.send_to_channel(
                    backup, notice, channels[backup]
                )
                self._audit.log_delivery(notice, result)
                self._store.record_delivery_outcome(
                    backup,
                    success=result.status == "delivered",
                    error=result.error,
                )

    async def dispatch_test(self, channel_type: str) -> DeliveryResult:
        from notification_service.models import sample_test_decision

        channels = self._router.get_channels()
        record = channels[channel_type]
        decision = sample_test_decision()
        return await self._channel_dispatcher.send_to_channel(
            channel_type, decision, record
        )
