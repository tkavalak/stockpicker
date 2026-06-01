from rule_engine.models import EnrichedMarketEvent, RuleConfig
from rule_engine.rules import evaluate_rules


def _event(**kwargs) -> EnrichedMarketEvent:
    base = {
        "symbol": "AAPL",
        "event_type": "trade",
        "price": 100.0,
        "volume": 1000.0,
        "timestamp_ns": 1,
        "raw_payload": {},
        "pct_change_1m": 0.5,
        "pct_change_5m": 1.0,
        "avg_volume_20": 500.0,
        "volume_ratio": 2.0,
        "volatility_score": 0.1,
    }
    base.update(kwargs)
    return EnrichedMarketEvent.from_dict(base)


def _configs() -> dict[str, RuleConfig]:
    return {
        "PRICE_SPIKE_5M": RuleConfig("PRICE_SPIKE_5M", True, 0.5, ["*"]),
    }


def test_price_spike_fires_above_threshold():
    event = _event(pct_change_5m=2.5)
    fires = evaluate_rules(event, _configs())
    assert len(fires) == 1
    assert fires[0].rule_name == "PRICE_SPIKE_5M"
    assert fires[0].triggered_value == 2.5


def test_volume_spike_config_ignored():
    configs = _configs()
    configs["VOLUME_SPIKE"] = RuleConfig("VOLUME_SPIKE", True, 0.5, ["*"])
    event = _event(pct_change_5m=0.1, volume_ratio=4.0)
    fires = evaluate_rules(event, configs)
    assert fires == []


def test_disabled_rule_does_not_fire():
    configs = _configs()
    configs["PRICE_SPIKE_5M"] = RuleConfig("PRICE_SPIKE_5M", False, 0.5, ["*"])
    fires = evaluate_rules(_event(pct_change_5m=5.0), configs)
    assert fires == []


def test_symbol_filter_excludes_non_matching():
    configs = _configs()
    configs["PRICE_SPIKE_5M"] = RuleConfig("PRICE_SPIKE_5M", True, 0.5, ["TSLA"])
    fires = evaluate_rules(_event(symbol="AAPL", pct_change_5m=5.0), configs)
    assert fires == []
