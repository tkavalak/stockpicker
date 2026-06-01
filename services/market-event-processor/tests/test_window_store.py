from market_event_processor.window_store import (
    InMemoryWindowStore,
    append_price,
    append_volume,
    trim_price_history,
)


def test_append_volume_caps_length():
    volumes = append_volume([1.0, 2.0], 3.0, max_len=3)
    assert volumes == [1.0, 2.0, 3.0]
    volumes = append_volume(volumes, 4.0, max_len=3)
    assert volumes == [2.0, 3.0, 4.0]


def test_trim_price_history():
    now = 10_000
    prices = [(1000, 1.0), (5000, 2.0), (9000, 3.0)]
    trimmed = trim_price_history(prices, now_ms=now)
    assert len(trimmed) >= 2


def test_in_memory_roundtrip():
    store = InMemoryWindowStore()
    from market_event_processor.window_store import SymbolWindow

    window = SymbolWindow(prices=[(1, 10.0)], volumes=[100.0])
    store.save_window("AAPL", window)
    loaded = store.get_window("AAPL")
    assert loaded.prices == [(1, 10.0)]
    assert loaded.volumes == [100.0]
