import pytest

from agentic_ai.governance.thresholds import GovernanceThresholds, load_governance_thresholds


def test_default_thresholds_valid():
    t = GovernanceThresholds(0.70, 0.90, 10.0)
    t.validate()


def test_escalation_must_exceed_confidence():
    t = GovernanceThresholds(0.80, 0.75, 10.0)
    with pytest.raises(ValueError, match="ESCALATION_THRESHOLD"):
        t.validate()


def test_load_from_env(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.6")
    monkeypatch.setenv("ESCALATION_THRESHOLD", "0.85")
    monkeypatch.setenv("COOLDOWN_WINDOW_MINUTES", "15")
    t = load_governance_thresholds()
    assert t.confidence_threshold == 0.6
    assert t.escalation_threshold == 0.85
    assert t.cooldown_minutes == 15
