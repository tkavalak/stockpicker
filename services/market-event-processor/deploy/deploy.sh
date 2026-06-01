#!/usr/bin/env bash
# Deploy Market Event Processor to Cloud Run (WO-6).
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVICE_DIR}/../.." && pwd)"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_REGION:=us-central1}"
: "${SERVICE_NAME:=market-event-processor}"
: "${REDIS_HOST:?Set REDIS_HOST (Memorystore IP from infra/config/streaming.env)}"
: "${VPC_CONNECTOR_NAME:=stockpickerdevconn}"

# shellcheck source=../../../scripts/gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

IMAGE="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest"

echo "==> Building image ${IMAGE}"
"${GCLOUD}" builds submit "${SERVICE_DIR}" --tag "${IMAGE}" --project="${GCP_PROJECT_ID}"

ENV_VARS="GCP_PROJECT_ID=${GCP_PROJECT_ID}"
ENV_VARS+=",PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR=market-event-processor-raw-market-events"
ENV_VARS+=",PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS=enriched-market-events"
ENV_VARS+=",REDIS_HOST=${REDIS_HOST}"
ENV_VARS+=",REDIS_PORT=${REDIS_PORT:-6379}"
ENV_VARS+=",ROLLING_WINDOW_SIZE=${ROLLING_WINDOW_SIZE:-20}"

echo "==> Deploying Cloud Run service ${SERVICE_NAME}"
echo "    VPC connector: ${VPC_CONNECTOR_NAME} (create via: ./infra/scripts/terraform.sh apply)"
"${GCLOUD}" run deploy "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${GCP_REGION}" \
  --image="${IMAGE}" \
  --platform=managed \
  --min-instances=1 \
  --max-instances=3 \
  --port=8080 \
  --timeout=600 \
  --cpu-boost \
  --vpc-connector="${VPC_CONNECTOR_NAME}" \
  --vpc-egress=private-ranges-only \
  --set-env-vars="${ENV_VARS}" \
  --allow-unauthenticated

echo "Deploy complete."
