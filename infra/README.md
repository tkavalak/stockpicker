# WO-4: GCP Streaming Infrastructure

Terraform and scripts to provision the Stock Picker streaming pipeline on GCP.

## Resources

| Resource | Details |
|----------|---------|
| **Pub/Sub topics** | `raw-market-events`, `enriched-market-events`, `trigger-events`, `alert-decisions` |
| **Dead-letter topics** | `raw-market-events-dlq`, `enriched-market-events-dlq` |
| **Subscriptions** | Consumer subs per service; DLQ monitor subs on both DLQ topics |
| **DLQ policy** | `max_delivery_attempts: 5` on raw and enriched consumer subscriptions |
| **Firestore** | Native database + collections `rule_configs`, `notification_configs`, `agent_state` |
| **Redis** | Memorystore STANDARD_HA, 1 GB, same region as Cloud Run |
| **Secret Manager** | `stock-picker-{env}-streaming-pipeline-config`, `stock-picker-{env}-redis-connection` |

### Pipeline topology

```
Polygon Streamer → raw-market-events → Market Event Processor
                 → enriched-market-events → Rule Engine
                 → trigger-events → Agentic AI
                 → alert-decisions → Notification Service
```

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.5
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated with permission to create Pub/Sub, Firestore, Redis, VPC, and Secret Manager resources
- Billing enabled on the target GCP project

## Provision

```bash
export GCP_PROJECT_ID=your-gcp-project-id
export GCP_REGION=us-central1          # optional, default us-central1
export ENVIRONMENT=dev                 # optional, default dev

cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project_id

cd ..
chmod +x scripts/provision.sh
./scripts/provision.sh
```

Or apply Terraform only:

```bash
cd infra/terraform
terraform init
terraform apply -var="project_id=${GCP_PROJECT_ID}"
```

Then seed Firestore:

```bash
pip install -r infra/scripts/requirements.txt
GCP_PROJECT_ID=your-project python infra/scripts/seed_firestore.py
```

## Firestore seed data

`rule_configs` documents:

| Document ID | threshold | enabled |
|-------------|-----------|---------|
| `PRICE_SPIKE_5M` | 2.0 | true |
| `VOLUME_SPIKE` | 3.0 | true |

## Config and secrets

After `provision.sh`:

- **Local env file:** `infra/config/streaming.env` (from Terraform outputs)
- **Secret Manager:** full JSON config at `stock-picker-{env}-streaming-pipeline-config`
- **Redis secret:** `stock-picker-{env}-redis-connection`

Cloud Run services (WO-5+) should mount secrets or source `streaming.env` at deploy time.

## Notes

- Redis requires the provisioned VPC; Cloud Run services need a VPC connector to reach Memorystore (configured in WO-5+ deployments).
- IAM for service accounts is out of scope for WO-4; assign per-service during Cloud Run deploy.
- `infra/terraform/.terraform/` and `terraform.tfvars` are gitignored; never commit secrets.
