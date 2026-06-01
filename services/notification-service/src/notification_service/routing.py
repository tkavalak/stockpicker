"""Evaluate routing rules for channel delivery."""

from __future__ import annotations

from notification_service.channels import ChannelRecord
from notification_service.models import ACTION_IGNORE, AlertDecision


def channels_for_decision(
    decision: AlertDecision,
    channels: dict[str, ChannelRecord],
) -> list[str]:
    if decision.action == ACTION_IGNORE:
        return []

    selected: list[str] = []
    for channel_type, record in channels.items():
        if not record.is_deliverable():
            continue
        rule = record.routing_rule
        if rule is None:
            selected.append(channel_type)
            continue
        if rule.matches(symbol=decision.symbol, action=decision.action):
            selected.append(channel_type)
    return selected
