"""Confidence, escalation, and cooldown threshold configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceThresholds:
    confidence_threshold: float
    escalation_threshold: float
    cooldown_minutes: float

    def validate(self) -> None:
        for name, value in (
            ("CONFIDENCE_THRESHOLD", self.confidence_threshold),
            ("ESCALATION_THRESHOLD", self.escalation_threshold),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0 (got {value})")
        if self.escalation_threshold <= self.confidence_threshold:
            raise ValueError(
                "ESCALATION_THRESHOLD must be greater than CONFIDENCE_THRESHOLD "
                f"({self.escalation_threshold} <= {self.confidence_threshold})"
            )
        if self.cooldown_minutes <= 0:
            raise ValueError(
                f"COOLDOWN_WINDOW_MINUTES must be positive (got {self.cooldown_minutes})"
            )


def load_governance_thresholds() -> GovernanceThresholds:
    thresholds = GovernanceThresholds(
        confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.70")),
        escalation_threshold=float(os.environ.get("ESCALATION_THRESHOLD", "0.90")),
        cooldown_minutes=float(os.environ.get("COOLDOWN_WINDOW_MINUTES", "10")),
    )
    thresholds.validate()
    return thresholds
