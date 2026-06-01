import pytest

from agentic_ai.llm.raw_decision import (
    PARSE_FAILURE_REASON,
    default_raw_decision,
    parse_raw_decision_response,
)


def test_parse_valid_json():
    raw = parse_raw_decision_response(
        '{"confidence": 0.85, "reason": "Strong volume spike.", "action_candidate": "ALERT"}',
        event_id="e1",
        symbol="AAPL",
        signal="VOLUME_SPIKE",
        provider="vertex_ai",
    )
    assert raw.confidence == 0.85
    assert raw.action_candidate == "ALERT"
    assert raw.reason == "Strong volume spike."


def test_parse_strips_markdown_fence():
    raw = parse_raw_decision_response(
        '```json\n{"confidence": 0.5, "reason": "ok", "action_candidate": "IGNORE"}\n```',
        symbol="X",
        signal="R",
    )
    assert raw.action_candidate == "IGNORE"


def test_parse_invalid_action_raises():
    with pytest.raises(ValueError):
        parse_raw_decision_response(
            '{"confidence": 0.5, "reason": "x", "action_candidate": "MAYBE"}'
        )


def test_default_raw_decision():
    raw = default_raw_decision(
        event_id="e1", symbol="AAPL", signal="R", reason=PARSE_FAILURE_REASON
    )
    assert raw.confidence == 0.0
    assert raw.action_candidate == "IGNORE"
