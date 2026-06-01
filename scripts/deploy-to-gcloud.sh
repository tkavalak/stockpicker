#!/usr/bin/env bash
# Deploy Stock Picker services to Cloud Run using repo-bundled gcloud (no global install).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"

# shellcheck source=gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env}"
export GCP_PROJECT_ID
export GCP_REGION="${GCP_REGION:-us-central1}"

echo "Using gcloud: ${GCLOUD}"
echo "Project: ${GCP_PROJECT_ID}  Region: ${GCP_REGION}"
echo ""

echo "==> Granting Cloud Run runtime access to Secret Manager"
bash "${REPO_ROOT}/scripts/grant-cloud-run-secrets.sh"

echo "==> Enabling required APIs (if needed)"
"${GCLOUD}" services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project="${GCP_PROJECT_ID}" \
  --quiet

"${REPO_ROOT}/scripts/configure-business-run.sh"

if [[ -f "${REPO_ROOT}/infra/config/streaming.env" ]]; then
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/infra/config/streaming.env"
  export REDIS_HOST="${REDIS_HOST:-}"
fi

deploy_one() {
  local name="$1"
  local script="$2"
  echo ""
  echo "========== Deploying ${name} =========="
  bash "${script}"
}

deploy_one "polygon-streamer" "${REPO_ROOT}/services/polygon-streamer/deploy/deploy.sh"

if [[ -z "${REDIS_HOST:-}" ]]; then
  echo ""
  echo "WARN: REDIS_HOST not set — skipping market-event-processor."
  echo "      Set REDIS_HOST from infra/config/streaming.env after terraform, then run:"
  echo "      REDIS_HOST=10.x.x.x ./services/market-event-processor/deploy/deploy.sh"
else
  export REDIS_HOST
  deploy_one "market-event-processor" "${REPO_ROOT}/services/market-event-processor/deploy/deploy.sh"
fi

deploy_one "rule-engine" "${REPO_ROOT}/services/rule-engine/deploy/deploy.sh"
deploy_one "agentic-ai-service" "${REPO_ROOT}/services/agentic-ai-service/deploy/deploy.sh"
deploy_one "notification-service" "${REPO_ROOT}/services/notification-service/deploy/deploy.sh"

echo ""
echo "==> Cloud Run services"
"${GCLOUD}" run services list --project="${GCP_PROJECT_ID}" --region="${GCP_REGION}"

echo ""
echo "Deploy complete."
