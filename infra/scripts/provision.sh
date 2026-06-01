#!/usr/bin/env bash
# Provision WO-4 GCP streaming infrastructure (Terraform + Firestore seed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
TF_DIR="${ROOT}/terraform"
SCRIPT_DIR="${ROOT}/scripts"
# shellcheck source=../../scripts/gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
  echo "ERROR: Set GCP_PROJECT_ID or create infra/terraform/terraform.tfvars with project_id" >&2
  exit 1
fi

gcp_check_auth || exit 1

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: terraform not found. Run: curl -fsSL ... (see infra/README.md) or use .tools/terraform" >&2
  exit 1
fi

if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "ERROR: GCP credentials not found." >&2
  echo "Run once (uses project-local config at .gcloud/):" >&2
  echo "  export CLOUDSDK_CONFIG=\"${CLOUDSDK_CONFIG}\"" >&2
  echo "  gcloud auth login" >&2
  echo "  gcloud auth application-default login --project=${GCP_PROJECT_ID}" >&2
  exit 1
fi

echo "==> Using GCP project: ${GCP_PROJECT_ID}"
gcloud config set project "${GCP_PROJECT_ID}" >/dev/null

echo "==> Terraform init"
terraform -chdir="${TF_DIR}" init

echo "==> Terraform apply"
terraform -chdir="${TF_DIR}" apply \
  -var="project_id=${GCP_PROJECT_ID}" \
  ${GCP_REGION:+-var="region=${GCP_REGION}"} \
  ${ENVIRONMENT:+-var="environment=${ENVIRONMENT}"} \
  "$@"

echo "==> Seed Firestore"
if [[ -d "${SCRIPT_DIR}/.venv" ]]; then
  "${SCRIPT_DIR}/.venv/bin/pip" install -q -r "${SCRIPT_DIR}/requirements.txt"
  GCP_PROJECT_ID="${GCP_PROJECT_ID}" "${SCRIPT_DIR}/.venv/bin/python" "${SCRIPT_DIR}/seed_firestore.py"
else
  python3 -m pip install -q -r "${SCRIPT_DIR}/requirements.txt"
  GCP_PROJECT_ID="${GCP_PROJECT_ID}" python3 "${SCRIPT_DIR}/seed_firestore.py"
fi

echo "==> Write local env config from Terraform outputs"
CONFIG_PATH="${ROOT}/config/streaming.env"
terraform -chdir="${TF_DIR}" output -json streaming_config | python3 -c "
import json, os, sys
cfg = json.load(sys.stdin)
lines = [
    f'GCP_PROJECT_ID={cfg[\"project_id\"]}',
    f'GCP_REGION={cfg[\"region\"]}',
    f'ENVIRONMENT={cfg[\"environment\"]}',
    '',
    f'PUBSUB_TOPIC_RAW_MARKET_EVENTS={cfg[\"pubsub\"][\"topics\"][\"raw_market_events\"]}',
    f'PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS={cfg[\"pubsub\"][\"topics\"][\"enriched_market_events\"]}',
    f'PUBSUB_TOPIC_TRIGGER_EVENTS={cfg[\"pubsub\"][\"topics\"][\"trigger_events\"]}',
    f'PUBSUB_TOPIC_ALERT_DECISIONS={cfg[\"pubsub\"][\"topics\"][\"alert_decisions\"]}',
    f'PUBSUB_TOPIC_RAW_DLQ={cfg[\"pubsub\"][\"topics\"][\"raw_market_events_dlq\"]}',
    f'PUBSUB_TOPIC_ENRICHED_DLQ={cfg[\"pubsub\"][\"topics\"][\"enriched_market_events_dlq\"]}',
    '',
    f'PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR={cfg[\"pubsub\"][\"subscriptions\"][\"market_event_processor\"]}',
    f'PUBSUB_SUBSCRIPTION_RULE_ENGINE={cfg[\"pubsub\"][\"subscriptions\"][\"rule_engine\"]}',
    f'PUBSUB_SUBSCRIPTION_AGENTIC_AI={cfg[\"pubsub\"][\"subscriptions\"][\"agentic_ai\"]}',
    f'PUBSUB_SUBSCRIPTION_NOTIFICATION={cfg[\"pubsub\"][\"subscriptions\"][\"notification\"]}',
    '',
    f'FIRESTORE_DATABASE={cfg[\"firestore\"][\"database_id\"]}',
    f'FIRESTORE_COLLECTION_RULE_CONFIGS=rule_configs',
    f'FIRESTORE_COLLECTION_NOTIFICATION_CONFIGS=notification_configs',
    f'FIRESTORE_COLLECTION_AGENT_STATE=agent_state',
    '',
    f'REDIS_HOST={cfg[\"redis\"][\"host\"]}',
    f'REDIS_PORT={cfg[\"redis\"][\"port\"]}',
    f'REDIS_CONNECTION_STRING={cfg[\"redis\"][\"connection_string\"]}',
    '',
    'SECRET_STREAMING_PIPELINE_CONFIG=' + os.environ.get('SECRET_STREAMING_PIPELINE_CONFIG', ''),
]
print('\n'.join(lines))
" > "${CONFIG_PATH}.tmp"

SECRET_ID="$(terraform -chdir="${TF_DIR}" output -json secret_ids | python3 -c "import json,sys; print(json.load(sys.stdin)['streaming_pipeline_config'])")"
sed "s|SECRET_STREAMING_PIPELINE_CONFIG=|SECRET_STREAMING_PIPELINE_CONFIG=${SECRET_ID}|" \
  "${CONFIG_PATH}.tmp" > "${CONFIG_PATH}"
rm -f "${CONFIG_PATH}.tmp"

echo "Provisioning complete. Config written to ${CONFIG_PATH}"
echo "Secret Manager: $(terraform -chdir="${TF_DIR}" output -json secret_ids)"
