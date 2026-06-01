from market_event_processor.metrics_calculator import MetricsCalculator
from market_event_processor.models import RawMarketEvent
from market_event_processor.window_store import InMemoryWindowStore


def _raw(
    symbol: str = "AAPL",
    price: float = 100.0,
    volume: float = 1000.0,
    ts_ns: int = 1_700_000_000_000_000_000,
) -> RawMarketEvent:
    return RawMarketEvent(
        symbol=symbol,
        event_type="trade",
        price=price,
        volume=volume,
        timestamp_ns=ts_ns,
        raw_payload={},
    )


def test_volume_ratio_after_warmup():
    store = InMemoryWindowStore()
    calc = MetricsCalculator(store)
    base_ts = 1_700_000_000_000_000_000

    for i in range(5):
        calc.enrich(
            _raw(volume=100.0, ts_ns=base_ts + i * 1_000_000_000)
        )

    enriched = calc.enrich(
        _raw(volume=400.0, ts_ns=base_ts + 6 * 1_000_000_000)
    )
    assert enriched.avg_volume_20 == 100.0
    assert enriched.volume_ratio == 4.0


def test_pct_change_5m():
    store = InMemoryWindowStore()
    calc = MetricsCalculator(store)
    t0 = 1_700_000_000_000_000_000
    five_min_ns = 5 * 60 * 1_000_000_000

    calc.enrich(_raw(price=100.0, ts_ns=t0))
    enriched = calc.enrich(_raw(price=103.0, ts_ns=t0 + five_min_ns))
    assert enriched.pct_change_5m is not None
    assert abs(enriched.pct_change_5m - 3.0) < 0.01


def test_state_persists_in_memory_store():
    store = InMemoryWindowStore()
    calc = MetricsCalculator(store)
    ts = 1_700_000_000_000_000_000
    calc.enrich(_raw(symbol="NVDA", volume=50.0, ts_ns=ts))
    window = store.get_window("NVDA")
    assert len(window.volumes) == 1
