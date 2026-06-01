#!/usr/bin/env bash
# Deploy Agentic AI Service to Cloud Run (WO-9).
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVICE_DIR}/../.." && pwd)"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

# shellcheck source=../../../scripts/gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

: "${GCP_REGION:=us-central1}"
: "${SERVICE_NAME:=agentic-ai-service}"

IMAGE="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest"

echo "==> Building image ${IMAGE}"
"${GCLOUD}" builds submit "${SERVICE_DIR}" --tag "${IMAGE}" --project="${GCP_PROJECT_ID}"

ENV_VARS="GCP_PROJECT_ID=${GCP_PROJECT_ID}"
ENV_VARS+=",PUBSUB_SUBSCRIPTION_AGENTIC_AI=agentic-ai-trigger-events"
ENV_VARS+=",PUBSUB_TOPIC_ALERT_DECISIONS=alert-decisions"
ENV_VARS+=",FIRESTORE_COLLECTION_AGENT_STATE=agent_state"
ENV_VARS+=",MAX_CONCURRENT_WORKFLOWS=${MAX_CONCURRENT_WORKFLOWS:-5}"
ENV_VARS+=",WORKFLOW_TIMEOUT_SEC=30"
if [[ -n "${POLYGON_API_KEY:-}" ]]; then
  ENV_VARS+=",POLYGON_API_KEY=${POLYGON_API_KEY}"
fi
if [[ -n "${NEWS_API_URL:-}" ]]; then
  ENV_VARS+=",NEWS_API_URL=${NEWS_API_URL}"
fi
ENV_VARS+=",VERTEX_AI_LOCATION=${VERTEX_AI_LOCATION:-${GCP_REGION}}"
ENV_VARS+=",VERTEX_AI_MODEL=${VERTEX_AI_MODEL:-gemini-1.5-flash}"
ENV_VARS+=",OPENAI_MODEL=${OPENAI_MODEL:-gpt-4o}"
ENV_VARS+=",CONFIDENCE_THRESHOLD=${CONFIDENCE_THRESHOLD:-0.70}"
ENV_VARS+=",ESCALATION_THRESHOLD=${ESCALATION_THRESHOLD:-0.90}"
ENV_VARS+=",COOLDOWN_WINDOW_MINUTES=${COOLDOWN_WINDOW_MINUTES:-10}"
if [[ -n "${AGENTIC_TEST_MODE:-}" ]]; then
  ENV_VARS+=",AGENTIC_TEST_MODE=${AGENTIC_TEST_MODE}"
fi

SECRETS=""
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  OPENAI_SECRET="${OPENAI_SECRET_NAME:-openai-api-key}"
  if ! "${GCLOUD}" secrets describe "${OPENAI_SECRET}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    "${GCLOUD}" secrets create "${OPENAI_SECRET}" --project="${GCP_PROJECT_ID}" --replication-policy=automatic
    printf '%s' "${OPENAI_API_KEY}" | "${GCLOUD}" secrets versions add "${OPENAI_SECRET}" \
      --project="${GCP_PROJECT_ID}" --data-file=-
  fi
  grant_secret_accessor "${OPENAI_SECRET}"
  SECRETS="OPENAI_API_KEY=${OPENAI_SECRET}:latest"
fi

DEPLOY_ARGS=(
  --project="${GCP_PROJECT_ID}"
  --region="${GCP_REGION}"
  --image="${IMAGE}"
  --platform=managed
  --min-instances=1
  --max-instances=3
  --port=8080
  --set-env-vars="${ENV_VARS}"
  --allow-unauthenticated
)
if [[ -n "${SECRETS}" ]]; then
  DEPLOY_ARGS+=(--set-secrets="${SECRETS}")
fi

echo "==> Deploying Cloud Run service ${SERVICE_NAME}"
"${GCLOUD}" run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

echo "Deploy complete."
