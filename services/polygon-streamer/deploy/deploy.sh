#!/usr/bin/env bash
# Build and deploy Polygon WebSocket Streamer to Cloud Run (WO-5).
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVICE_DIR}/../.." && pwd)"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${GCP_REGION:=us-central1}"
: "${SERVICE_NAME:=polygon-websocket-streamer}"
: "${WATCHED_SYMBOLS:?Set WATCHED_SYMBOLS (top S&P 500 tickers, comma-separated)}"

if [[ -z "${POLYGON_API_KEY:-}" ]]; then
  echo "ERROR: Set POLYGON_API_KEY for initial secret creation" >&2
  exit 1
fi

# shellcheck source=../../../scripts/gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

SECRET_NAME="${POLYGON_SECRET_NAME:-polygon-api-key}"
if ! "${GCLOUD}" secrets describe "${SECRET_NAME}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
  echo "==> Creating Secret Manager secret ${SECRET_NAME}"
  "${GCLOUD}" secrets create "${SECRET_NAME}" --project="${GCP_PROJECT_ID}" --replication-policy=automatic
  printf '%s' "${POLYGON_API_KEY}" | "${GCLOUD}" secrets versions add "${SECRET_NAME}" \
    --project="${GCP_PROJECT_ID}" --data-file=-
fi
grant_secret_accessor "${SECRET_NAME}"

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
  --max-instances=1 \
  --no-cpu-throttling \
  --port=8080 \
  --set-secrets="POLYGON_API_KEY=${SECRET_NAME}:latest" \
  --set-env-vars="^|^GCP_PROJECT_ID=${GCP_PROJECT_ID}|PUBSUB_TOPIC_RAW_MARKET_EVENTS=raw-market-events|WATCHED_SYMBOLS=${WATCHED_SYMBOLS}|POLYGON_WS_FEED=${POLYGON_WS_FEED:-Delayed}" \
  --allow-unauthenticated

echo "Deploy complete. Health:"
echo "  ${GCLOUD} run services describe ${SERVICE_NAME} --region=${GCP_REGION} --format='value(status.url)'"
