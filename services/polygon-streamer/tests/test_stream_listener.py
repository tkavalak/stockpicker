from polygon.websocket.models import Feed

from polygon_streamer.stream_listener import (
    build_subscriptions,
    parse_polygon_feed,
    polygon_log_events_enabled,
)


def test_build_subscriptions_aggregates_only():
    assert build_subscriptions(["AAPL", "MSFT", "NVDA"]) == [
        "A.AAPL",
        "A.MSFT",
        "A.NVDA",
    ]


def test_parse_polygon_feed_defaults_to_delayed():
    assert parse_polygon_feed() == Feed.Delayed


def test_parse_polygon_feed_accepts_name():
    assert parse_polygon_feed("StarterFeed") == Feed.StarterFeed


def test_polygon_log_events_enabled(monkeypatch):
    monkeypatch.delenv("POLYGON_LOG_EVENTS", raising=False)
    assert polygon_log_events_enabled() is False
    monkeypatch.setenv("POLYGON_LOG_EVENTS", "1")
    assert polygon_log_events_enabled() is True
