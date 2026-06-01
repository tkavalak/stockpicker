from notification_service.channels import ChannelRecord, RoutingRule, STATUS_CONNECTED
from notification_service.channels import CHANNEL_EMAIL, CHANNEL_TEAMS
from notification_service.models import AlertDecision
from notification_service.routing import channels_for_decision


def _decision(symbol: str = "AAPL", action: str = "ALERT") -> AlertDecision:
    return AlertDecision(
        decision_id="d1",
        symbol=symbol,
        action=action,
        signal_type="PRICE_SPIKE_5M",
        measured_magnitude=2.0,
        confidence_score=0.9,
        reason="test",
        event_timestamp="2026-01-01T00:00:00Z",
    )


def _record(
    channel_type: str,
    *,
    rule: RoutingRule | None = None,
    status: str = STATUS_CONNECTED,
) -> ChannelRecord:
    return ChannelRecord(
        channel_type=channel_type,
        status=status,
        enabled=True,
        consecutive_failures=0,
        last_verified_at=None,
        routing_rule=rule,
        credentials={"ok": True},
    )


def test_no_rule_receives_all():
    channels = {
        CHANNEL_EMAIL: _record(CHANNEL_EMAIL),
        CHANNEL_TEAMS: _record(CHANNEL_TEAMS),
    }
    result = channels_for_decision(_decision(), channels)
    assert CHANNEL_EMAIL in result
    assert CHANNEL_TEAMS in result


def test_symbol_filter():
    rule = RoutingRule(symbols=("NVDA",), actions=())
    channels = {CHANNEL_EMAIL: _record(CHANNEL_EMAIL, rule=rule)}
    assert channels_for_decision(_decision("AAPL"), channels) == []
    assert CHANNEL_EMAIL in channels_for_decision(_decision("NVDA"), channels)


def test_action_filter_escalate_only():
    rule = RoutingRule(symbols=(), actions=("ESCALATE",))
    channels = {CHANNEL_EMAIL: _record(CHANNEL_EMAIL, rule=rule)}
    assert channels_for_decision(_decision(action="ALERT"), channels) == []
    assert CHANNEL_EMAIL in channels_for_decision(_decision(action="ESCALATE"), channels)
