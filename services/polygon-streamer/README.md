# Polygon WebSocket Streamer (WO-5)

Cloud Run service that streams Polygon.io trades and aggregates to Pub/Sub `raw-market-events`.

## Components

| Component | Role |
|-----------|------|
| `PolygonStreamListener` | WebSocket lifecycle, subscriptions, exponential back-off reconnect |
| `PubSubPublisher` | Publishes `MarketEventMessage` JSON envelopes with retries |
| `StreamAdminController` | `GET /health` (200 connected / 503 disconnected), `GET /symbols` |

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `POLYGON_API_KEY` | Yes | Polygon.io API key (Secret Manager in prod) |
| `GCP_PROJECT_ID` | Yes | GCP project |
| `WATCHED_SYMBOLS` | Yes | Comma-separated tickers |
| `PUBSUB_TOPIC_RAW_MARKET_EVENTS` | No | Default `raw-market-events` |
| `POLYGON_POST_DISCONNECT_DELAY_SEC` | No | Min seconds between close and reconnect (default `10`) |
| `POLYGON_POLICY_VIOLATION_EXTRA_SEC` | No | Extra delay after 1008 errors (default `20`) |

## Local run

```bash
cd services/polygon-streamer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
export GCP_PROJECT_ID=stockadvisor-498000
export POLYGON_API_KEY=your_key
export WATCHED_SYMBOLS=AAPL,MSFT,NVDA,AMZN,GOOGL,META,BRK.B,TSLA,LLY,AVGO,JPM,V,UNH,XOM,WMT,MA,PG,COST,HD,NFLX
python -m polygon_streamer.main
```

## Tests

```bash
pip install -r requirements.txt pytest
PYTHONPATH=src pytest tests/ -q
```

## Deploy (Cloud Run, min-instances=1)

```bash
export GCP_PROJECT_ID=stockadvisor-498000
export GCP_REGION=us-central1
export POLYGON_API_KEY=your_key
export WATCHED_SYMBOLS=AAPL,MSFT,NVDA,AMZN,GOOGL,META,BRK.B,TSLA,LLY,AVGO,JPM,V,UNH,XOM,WMT,MA,PG,COST,HD,NFLX
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Requires WO-4 infrastructure and `gcloud` auth (see `infra/scripts/auth-gcp.sh`).
