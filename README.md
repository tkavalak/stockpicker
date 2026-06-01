# Stock Picker

## Phase 1 POC (WO-1 + WO-2 + WO-3)

End-to-end proof-of-concept: Polygon WebSocket ingestion → in-process rule evaluation → SMTP email alerts.

## Rule engine (WO-2)

`rule_engine.evaluate_rules(event)` runs synchronously on each parsed event:

- **PRICE_SPIKE_5M** — fires when 5-minute price change exceeds 2.0%
- **VOLUME_SPIKE** — fires when volume exceeds 3.0× the rolling 20-event average

Fired rules are logged as `ALERT` lines with symbol, rule name, measured value, threshold, and timestamp.

## Email alerts (WO-3)

When a rule fires, `send_alert_email` sends a plain-text SMTP message:

- Subject: `[StockPicker POC] {symbol} {rule_name} triggered`
- Body: symbol, rule name, measured value, threshold, event timestamp

Configure in `.env`:

- `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_USER`, `SMTP_PASS`, `ALERT_TO_EMAIL`

Success and failure are logged as `EMAIL alert sent` / `EMAIL alert failed` on stdout.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

### Full business pipeline (Phase 2)

Starts all five services, seeds Firestore rules, and enables email from `.env`:

```bash
./scripts/run-pipeline.sh
# Stop: ./scripts/stop-pipeline.sh
```

Health: streamer `:8080`, market-event-processor `:8084`, rule-engine `:8081`, agentic-ai `:8082`, notification `:8083`. Logs under `.logs/pipeline/`.

### Phase 1 POC

```bash
# .env is loaded automatically (see .env.example)
python polygon_ws_poc.py
```

On disconnect, the script waits 5 seconds, retries once, and re-subscribes to all watchlist symbols.

## Phase 2 services

### Polygon WebSocket Streamer (WO-5)

Production service under [`services/polygon-streamer/`](services/polygon-streamer/README.md) — WebSocket → Pub/Sub `raw-market-events`, admin `/health` and `/symbols`, Cloud Run `min-instances=1`.

### Market Event Processor (WO-6)

[`services/market-event-processor/`](services/market-event-processor/README.md) — consumes `raw-market-events`, enriches metrics (Redis or in-memory locally), publishes `enriched-market-events`.

### Rule Engine (WO-7)

[`services/rule-engine/`](services/rule-engine/README.md) — consumes `enriched-market-events`, evaluates Firestore-backed rules, publishes `trigger-events`. Admin `/health` and `/rules`.

### Notification Service (WO-8)

[`services/notification-service/`](services/notification-service/README.md) — consumes `alert-decisions`, fan-out to SendGrid email (Slack disabled), audit log in BigQuery.

### Agentic AI Service (WO-9)

[`services/agentic-ai-service/`](services/agentic-ai-service/README.md) — Full LangGraph pipeline through ControlAgent governance (WO-9–12).

## Phase 2 infrastructure (WO-4)

GCP streaming pipeline provisioning (Pub/Sub, Firestore, Memorystore Redis, Secret Manager) lives under [`infra/`](infra/README.md).

```bash
export GCP_PROJECT_ID=your-gcp-project-id
./infra/scripts/provision.sh
```

## GCP setup (required for Terraform and Phase 2 services)

Tools live under `.tools/` and credentials under `.gcloud/`. One-time auth:

```bash
cd /Users/home/Downloads/Test80909
chmod +x infra/scripts/auth-gcp.sh infra/scripts/terraform.sh
./infra/scripts/auth-gcp.sh
```

You do **not** need a global `gcloud` install. Use repo wrappers:

```bash
./infra/scripts/gcloud.sh run services list --project=stockadvisor-498000 --region=us-central1
./infra/scripts/terraform.sh apply
```

### Deploy all services to Cloud Run

```bash
cd /Users/home/Downloads/Test80909
set -a && source .env && set +a
chmod +x scripts/deploy-to-gcloud.sh
./scripts/deploy-to-gcloud.sh
```

Or deploy one service (each script bundles gcloud automatically):

```bash
set -a && source .env && set +a
./services/polygon-streamer/deploy/deploy.sh
```

Local run (no global gcloud):

```bash
./services/market-event-processor/run.sh
./services/rule-engine/run.sh
```

## Troubleshooting

| Error | Cause | Fix |
|-------|--------|-----|
| `No module named 'aiohttp'` | Repo root `.venv` used for a service | `./services/rule-engine/run.sh` |
| `No module named 'polygon'` in tests | Wrong venv | `./services/polygon-streamer/test.sh` |
| `command not found: terraform` | Terraform not on global PATH | `./infra/scripts/terraform.sh apply` |
| `command not found: gcloud` | Bare `gcloud` not on PATH | `source scripts/gcp-env.sh` then `gcloud ...`, or `./infra/scripts/gcloud.sh ...` |
| `No module named 'agentic_ai'` | Wrong venv / ran a `.py` file directly | `./services/agentic-ai-service/run.sh` (not `python .../signal_agent.py`) |
| `DefaultCredentialsError` / ADC not found | Ran a script without repo GCP env | `./infra/scripts/auth-gcp.sh` once, then `./scripts/configure-business-run.sh` or any `services/*/run.sh` (not bare `python3` without `source scripts/gcp-env.sh`) |
| `address already in use` port 8080 | Stale service or another app on 8080 | `lsof -i :8080` and stop it, or `PORT=8081 ./services/rule-engine/run.sh` (run.sh auto-picks 8081) |
| `websocket access` Polygon `AuthError` | API plan lacks WebSocket | Upgrade Polygon plan (not fixable in code) |
| `--set-env-vars` Bad syntax `[MSFT]` | Commas in `WATCHED_SYMBOLS` | Fixed in `polygon-streamer/deploy/deploy.sh` (uses `\|^` delimiter); redeploy |
| Secret Manager `Permission denied` on deploy | Cloud Run SA lacks `secretAccessor` | `./scripts/grant-cloud-run-secrets.sh` then redeploy |
| Cloud Run `failed to start` on port 8080 (market-event-processor) | Redis ping before HTTP or no VPC to Memorystore | `./infra/scripts/terraform.sh apply` then redeploy with `REDIS_HOST` + VPC connector |
