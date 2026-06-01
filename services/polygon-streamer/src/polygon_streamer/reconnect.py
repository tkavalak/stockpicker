"""Exponential back-off for WebSocket reconnection."""

from __future__ import annotations

import os

INITIAL_RECONNECT_SEC = 5.0
MAX_RECONNECT_DELAY_SEC = 60.0
BACKOFF_MULTIPLIER = 2.0
STREAM_UNAVAILABLE_NOTIFY_SEC = 60.0
# Minimum pause after any close before opening a new socket (avoids overlapping sessions).
POST_DISCONNECT_DELAY_SEC = float(os.environ.get("POLYGON_POST_DISCONNECT_DELAY_SEC", "10"))
POLICY_VIOLATION_EXTRA_SEC = float(
    os.environ.get("POLYGON_POLICY_VIOLATION_EXTRA_SEC", "20")
)
STABLE_SESSION_SEC = float(os.environ.get("POLYGON_STABLE_SESSION_SEC", "30"))


def reconnect_delay_seconds(
    attempt: int,
    *,
    initial: float = INITIAL_RECONNECT_SEC,
    multiplier: float = BACKOFF_MULTIPLIER,
    max_delay: float = MAX_RECONNECT_DELAY_SEC,
    policy_violation: bool = False,
) -> float:
    """
    Seconds to wait after a session closes before the next connect.

    `attempt` is the number of consecutive unstable sessions (1 = first failure).
    Always at least POST_DISCONNECT_DELAY_SEC so Polygon can release the prior socket.
    """
    if attempt < 1:
        delay = POST_DISCONNECT_DELAY_SEC
    else:
        backoff = initial * (multiplier ** (attempt - 1))
        delay = max(POST_DISCONNECT_DELAY_SEC, backoff)
    delay = min(delay, max_delay)
    if policy_violation:
        delay = min(delay + POLICY_VIOLATION_EXTRA_SEC, max_delay)
    return delay


def is_policy_violation(error: str | None) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return "1008" in error or "policy violation" in lowered
