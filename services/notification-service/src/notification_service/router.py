"""Route AlertDecision messages to enabled delivery channels."""

from __future__ import annotations

from notification_service.config_loader import NotificationConfigLoader
from notification_service.models import AlertDecision
from notification_service.routing import channels_for_decision


class NotificationRouter:
    def __init__(self, config_loader: NotificationConfigLoader) -> None:
        self._config_loader = config_loader

    def channels_for(self, decision: AlertDecision) -> list[str]:
        channels = self._config_loader.get_channels()
        return channels_for_decision(decision, channels)

    def config_snapshot(self) -> dict:
        channels = self._config_loader.get_channels()
        return {k: v.to_public_dict() for k, v in channels.items()}

    def get_channels(self) -> dict:
        return self._config_loader.get_channels()
