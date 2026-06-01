#!/usr/bin/env bash
# Deploy Rule Engine Service to Cloud Run (WO-7).
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVICE_DIR}/../.." && pwd)"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_REGION:=us-central1}"
: "${SERVICE_NAME:=rule-engine}"

# shellcheck source=../../../scripts/gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

IMAGE="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest"

echo "==> Building image ${IMAGE}"
"${GCLOUD}" builds submit "${SERVICE_DIR}" --tag "${IMAGE}" --project="${GCP_PROJECT_ID}"

echo "==> Deploying Cloud Run service ${SERVICE_NAME}"
"${GCLOUD}" run deploy "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${GCP_REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --min-instances=1 \
  --max-instances=3 \
  --port=8080 \
  --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT_ID},PUBSUB_SUBSCRIPTION_RULE_ENGINE=rule-engine-enriched-market-events,PUBSUB_TOPIC_TRIGGER_EVENTS=trigger-events,FIRESTORE_COLLECTION_RULE_CONFIGS=rule_configs" \
  --allow-unauthenticated

echo "Deploy complete."
