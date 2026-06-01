from polygon_streamer.reconnect import (
    INITIAL_RECONNECT_SEC,
    MAX_RECONNECT_DELAY_SEC,
    POST_DISCONNECT_DELAY_SEC,
    POLICY_VIOLATION_EXTRA_SEC,
    STREAM_UNAVAILABLE_NOTIFY_SEC,
    is_policy_violation,
    reconnect_delay_seconds,
)


def test_first_reconnect_uses_post_disconnect_minimum():
    assert reconnect_delay_seconds(1) == POST_DISCONNECT_DELAY_SEC
    assert reconnect_delay_seconds(1) >= INITIAL_RECONNECT_SEC


def test_exponential_backoff_grows():
    assert reconnect_delay_seconds(2) == max(POST_DISCONNECT_DELAY_SEC, 10.0)
    assert reconnect_delay_seconds(3) == max(POST_DISCONNECT_DELAY_SEC, 20.0)


def test_backoff_caps_at_max():
    assert reconnect_delay_seconds(10) == MAX_RECONNECT_DELAY_SEC


def test_zero_attempt_uses_post_disconnect():
    assert reconnect_delay_seconds(0) == POST_DISCONNECT_DELAY_SEC


def test_policy_violation_adds_extra_delay():
    base = reconnect_delay_seconds(1, policy_violation=False)
    extra = reconnect_delay_seconds(1, policy_violation=True)
    assert extra == min(base + POLICY_VIOLATION_EXTRA_SEC, MAX_RECONNECT_DELAY_SEC)


def test_is_policy_violation():
    assert is_policy_violation("received 1008 (policy violation)")
    assert not is_policy_violation("connection reset")


def test_stream_unavailable_threshold():
    assert STREAM_UNAVAILABLE_NOTIFY_SEC == 60.0
