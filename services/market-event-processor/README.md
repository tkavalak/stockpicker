# Market Event Processor (WO-6)

Consumes `raw-market-events`, computes rolling metrics (price change, volume ratio, volatility), and publishes `EnrichedMarketEvent` messages to `enriched-market-events` for the Rule Engine.

## Components

| Component | Role |
|-----------|------|
| `MarketEventConsumer` | Pub/Sub pull on `market-event-processor-raw-market-events`; ack after publish |
| `MetricsCalculator` | `pct_change_1m`, `pct_change_5m`, `avg_volume_20`, `volume_ratio`, `volatility_score` |
| `WindowStore` | Redis (`mep:{symbol}:*`) in prod; in-memory when `REDIS_HOST` unset |
| `EnrichedEventPublisher` | Publishes to `enriched-market-events` |
| `MarketEventAdmin` | `GET /health` — 503 if window store unreachable |

Malformed raw messages are acked and logged. Redis/publish failures nack for retry (DLQ after max attempts).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | required | GCP project |
| `PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR` | `market-event-processor-raw-market-events` | Inbound subscription |
| `PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS` | `enriched-market-events` | Outbound topic |
| `REDIS_HOST` | — | Memorystore host (prod) |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_USE_MEMORY` | `1` if no `REDIS_HOST` | Force in-memory store |
| `ROLLING_WINDOW_SIZE` | `20` | Volume rolling window events |
| `PORT` | `8080` | Admin HTTP |

## Local run

```bash
./services/market-event-processor/run.sh
```

Uses in-memory windows by default so you do not need Memorystore locally. For Redis:

```bash
docker run -d -p 6379:6379 redis:7-alpine
export REDIS_HOST=127.0.0.1
export REDIS_USE_MEMORY=0
./services/market-event-processor/run.sh
```

Requires WO-4 Pub/Sub topics and `./services/polygon-streamer/run.sh` publishing raw events.

## Tests

```bash
cd services/market-event-processor
pip install -r requirements.txt pytest
PYTHONPATH=src pytest tests/ -q
```

## Deploy

```bash
export GCP_PROJECT_ID=stockadvisor-498000
export REDIS_HOST=10.0.0.3   # from infra/config/streaming.env
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

`min-instances=1` keeps enrichment warm.

**Cloud Run + Redis:** Memorystore is on a private VPC. Apply Terraform (creates `stockpickerdevconn` VPC connector), then deploy:

```bash
grep REDIS_HOST infra/config/streaming.env
export REDIS_HOST=10.x.x.x
export VPC_CONNECTOR_NAME=stockpickerdevconn   # default; from terraform output vpc_connector_name
./services/market-event-processor/deploy/deploy.sh
```

Without the VPC connector, the container may fail Cloud Run startup or cannot reach Redis.
