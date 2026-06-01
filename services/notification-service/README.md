# Notification Service (WO-8, WO-13)

Delivers `AlertDecision` messages from `alert-decisions` to connected channels with routing rules, failure tracking, and a channel management API.

## Channels

| Channel | Adapter | Credentials (via `POST /channels`) |
|---------|---------|-------------------------------------|
| **Pushover** | Push API | `user_key` (or `PUSHOVER_USER_KEY` env); `PUSHOVER_APP_TOKEN` env |
| Email | SendGrid | `to_email`, optional `from_email` (API key from env) |
| Slack | `chat.postMessage` | `channel_id` (bot token from env; HTTP path disabled by default) |
| Teams | Incoming Webhook | `webhook_url` |
| Twilio | SMS / WhatsApp | `account_sid`, `auth_token`, `from_number`, `to_number`, optional `mode` (`sms` or `whatsapp`) |

Teams and Twilio retry up to 3× on transient errors. Slack remains log-only until `slack_adapter.py` HTTP is uncommented.

## Components

| Component | Role |
|-----------|------|
| `NotificationConsumer` | Pub/Sub pull; acks after all channel attempts |
| `NotificationRouter` | Routing rules + deliverable channel filter |
| `NotificationConfigStore` | Firestore `notification_configs/default` (`channels` map) |
| `ChannelDispatcher` | Per-channel send (pushover, email, teams, twilio, slack) |
| `NotificationDispatcher` | Fan-out, audit, 3-strike → `error`, backup notify |
| `AuditLogger` | Rows in `stock_picker.notification_audit` |

Fan-out uses `asyncio.gather` — one channel failing does not block others.

## Routing rules

Per-channel `routing_rule` in Firestore:

- `symbols`: list of tickers (or `*`); empty = no symbol filter
- `actions`: `ALERT`, `ESCALATE`; empty = no action filter
- No rule → channel receives all non-`IGNORE` alerts

## Channel API (internal)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/channels` | List channels (no secrets) |
| `POST` | `/channels` | Connect: `{ "type", "credentials", "routing_rule"? }` — validates via test send |
| `DELETE` | `/channels/{type}` | Disconnect |
| `PUT` | `/channels/{type}/routing` | Update routing rule |
| `POST` | `/channels/{type}/test` | Test alert; updates `last_verified_at` or `error` |

Also: `GET /health` — consumer health + channel snapshot.

## Environment

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Required |
| `PUSHOVER_APP_TOKEN` | Pushover application API token |
| `PUSHOVER_USER_KEY` | Pushover user key (recipient) |
| `PUSHOVER_DEVICE` | Optional device name filter |
| `SENDGRID_API_KEY` | SendGrid API key (email channel only) |
| `SENDGRID_FROM_EMAIL` | Default sender (email) |
| `ALERT_TO_EMAIL` | Default recipient (email) |
| `SLACK_BOT_TOKEN` | Slack Bot token (optional) |
| `SLACK_CHANNEL_ID` | Target channel (optional) |
| `TWILIO_ACCOUNT_SID` | Twilio fallback env |
| `TWILIO_AUTH_TOKEN` | Twilio fallback env |
| `TWILIO_FROM_NUMBER` | Twilio fallback env |
| `TWILIO_TO_NUMBER` | Twilio fallback env |
| `TWILIO_MODE` | `sms` or `whatsapp` (default `sms`) |
| `BIGQUERY_DATASET` | Default `stock_picker` |
| `BIGQUERY_TABLE` | Default `notification_audit` |
| `FIRESTORE_COLLECTION_NOTIFICATION_CONFIGS` | Default `notification_configs` |

Channel credentials are normally stored in Firestore via the API; env vars support legacy migration and adapter fallbacks.

## Seed Firestore

```bash
python infra/scripts/seed_firestore.py
```

## Tests

```bash
cd services/notification-service
pip install -r requirements.txt pytest
PYTHONPATH=src pytest tests/ -q
```

## Deploy

```bash
export GCP_PROJECT_ID=stockadvisor-498000
export SENDGRID_API_KEY=...
export SENDGRID_FROM_EMAIL=alerts@example.com
export ALERT_TO_EMAIL=you@example.com
./deploy/deploy.sh
```

### Test Pushover

```bash
curl -s -X POST http://localhost:8083/channels/pushover/test | python3 -m json.tool
```

Connect first if needed:

```bash
curl -s -X POST http://localhost:8083/channels \
  -H 'Content-Type: application/json' \
  -d '{"type": "pushover", "credentials": {}}'
```

(Uses `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY` from the process environment.)

Connect Teams/Twilio at runtime via `POST /channels` after deploy. Scale-to-zero is acceptable (`min-instances=0`).
