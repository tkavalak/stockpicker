"""PRICE_SPIKE_5M rule evaluation."""

from __future__ import annotations

from rule_engine.models import (
    EnrichedMarketEvent,
    RuleConfig,
    RuleFire,
    symbol_matches,
)


def evaluate_rules(
    event: EnrichedMarketEvent,
    configs: dict[str, RuleConfig],
) -> list[RuleFire]:
    """
    Evaluate all enabled rules against an enriched event.

    `configs` should be snapshotted for the duration of one message (REQ-RMA-MDR-002.3).
    """
    fires: list[RuleFire] = []
    symbol = event.symbol

    price_cfg = configs.get("PRICE_SPIKE_5M")
    if (
        price_cfg
        and price_cfg.enabled
        and symbol_matches(symbol, price_cfg.symbols)
        and event.pct_change_5m is not None
        and event.pct_change_5m > price_cfg.threshold
    ):
        fires.append(
            RuleFire(
                rule_name="PRICE_SPIKE_5M",
                triggered_value=event.pct_change_5m,
                threshold_value=price_cfg.threshold,
            )
        )

    return fires
