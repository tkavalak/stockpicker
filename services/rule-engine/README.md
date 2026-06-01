# Rule Engine Service (WO-7)

Consumes `enriched-market-events`, evaluates `PRICE_SPIKE_5M` and `VOLUME_SPIKE` against Firestore-backed thresholds, and publishes `TriggerEvent` messages to `trigger-events`.

## Components

| Component | Role |
|-----------|------|
| `RuleEngineConsumer` | Pub/Sub pull on `rule-engine-enriched-market-events` |
| `RuleConfigLoader` | Firestore `rule_configs` with 30s TTL cache |
| `TriggerEventPublisher` | Publishes to `trigger-events` |
| `RuleEngineAdmin` | `GET /health`, `GET /rules` |

## Rules

| Rule | Condition | Default threshold |
|------|-----------|-------------------|
| `PRICE_SPIKE_5M` | `pct_change_5m > threshold` | 2.0% |
| `VOLUME_SPIKE` | `volume_ratio > threshold` | 3.0× |

Disabled rules and symbol filters (`*` or explicit tickers) are respected. Config changes apply within 30 seconds.

## Environment

| Variable | Default |
|----------|---------|
| `GCP_PROJECT_ID` | required |
| `PUBSUB_SUBSCRIPTION_RULE_ENGINE` | `rule-engine-enriched-market-events` |
| `PUBSUB_TOPIC_TRIGGER_EVENTS` | `trigger-events` |
| `FIRESTORE_COLLECTION_RULE_CONFIGS` | `rule_configs` |
| `PORT` | `8080` |

## Local run

```bash
cd services/rule-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
export PYTHONPATH=src
export GCP_PROJECT_ID=stockadvisor-498000
python -m rule_engine.main
```

## Tests

```bash
PYTHONPATH=src pytest tests/ -q
```

## Deploy

```bash
export GCP_PROJECT_ID=stockadvisor-498000
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Requires WO-4 infrastructure and a running Market Event Processor publishing enriched events.
