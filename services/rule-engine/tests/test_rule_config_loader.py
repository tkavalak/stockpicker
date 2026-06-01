from unittest.mock import MagicMock

from rule_engine.models import DEFAULT_THRESHOLDS
from rule_engine.rule_config_loader import RuleConfigLoader


def test_defaults_when_firestore_empty():
    mock_client = MagicMock()
    mock_client.collection.return_value.stream.return_value = []

    loader = RuleConfigLoader(client=mock_client)
    configs = loader.get_configs(force_reload=True)

    assert configs["PRICE_SPIKE_5M"].threshold == DEFAULT_THRESHOLDS["PRICE_SPIKE_5M"]
    assert configs["PRICE_SPIKE_5M"].enabled is True
    assert "VOLUME_SPIKE" not in configs
