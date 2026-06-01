#!/usr/bin/env bash
# Deploy Notification Service to Cloud Run (WO-8, WO-13).
set -euo pipefail

SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SERVICE_DIR}/../.." && pwd)"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

# shellcheck source=../../../scripts/gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

: "${GCP_REGION:=us-central1}"
: "${SERVICE_NAME:=notification-service}"

IMAGE="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest"

echo "==> Building image ${IMAGE}"
"${GCLOUD}" builds submit "${SERVICE_DIR}" --tag "${IMAGE}" --project="${GCP_PROJECT_ID}"

ENV_VARS="GCP_PROJECT_ID=${GCP_PROJECT_ID}"
ENV_VARS+=",PUBSUB_SUBSCRIPTION_NOTIFICATION=notification-alert-decisions"
ENV_VARS+=",BIGQUERY_DATASET=stock_picker"
ENV_VARS+=",BIGQUERY_TABLE=notification_audit"
ENV_VARS+=",FIRESTORE_COLLECTION_NOTIFICATION_CONFIGS=notification_configs"

SECRETS=""
# Slack deploy disabled until slack_adapter.py HTTP block is uncommented.
# if [[ -n "${SLACK_BOT_TOKEN:-}" ]]; then
#   SECRET_NAME="${SLACK_SECRET_NAME:-slack-bot-token}"
#   if ! gcloud secrets describe "${SECRET_NAME}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
#     gcloud secrets create "${SECRET_NAME}" --project="${GCP_PROJECT_ID}" --replication-policy=automatic
#     printf '%s' "${SLACK_BOT_TOKEN}" | gcloud secrets versions add "${SECRET_NAME}" \
#       --project="${GCP_PROJECT_ID}" --data-file=-
#   fi
#   SECRETS="SLACK_BOT_TOKEN=${SECRET_NAME}:latest"
# fi
if [[ -n "${PUSHOVER_APP_TOKEN:-}" ]]; then
  PO_APP_SECRET="${PUSHOVER_APP_SECRET_NAME:-pushover-app-token}"
  if ! "${GCLOUD}" secrets describe "${PO_APP_SECRET}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    "${GCLOUD}" secrets create "${PO_APP_SECRET}" --project="${GCP_PROJECT_ID}" --replication-policy=automatic
    printf '%s' "${PUSHOVER_APP_TOKEN}" | "${GCLOUD}" secrets versions add "${PO_APP_SECRET}" \
      --project="${GCP_PROJECT_ID}" --data-file=-
  fi
  grant_secret_accessor "${PO_APP_SECRET}"
  SECRETS="PUSHOVER_APP_TOKEN=${PO_APP_SECRET}:latest"
fi
if [[ -n "${PUSHOVER_USER_KEY:-}" ]]; then
  PO_USER_SECRET="${PUSHOVER_USER_SECRET_NAME:-pushover-user-key}"
  if ! "${GCLOUD}" secrets describe "${PO_USER_SECRET}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    "${GCLOUD}" secrets create "${PO_USER_SECRET}" --project="${GCP_PROJECT_ID}" --replication-policy=automatic
    printf '%s' "${PUSHOVER_USER_KEY}" | "${GCLOUD}" secrets versions add "${PO_USER_SECRET}" \
      --project="${GCP_PROJECT_ID}" --data-file=-
  fi
  grant_secret_accessor "${PO_USER_SECRET}"
  if [[ -n "${SECRETS}" ]]; then
    SECRETS+=",PUSHOVER_USER_KEY=${PO_USER_SECRET}:latest"
  else
    SECRETS="PUSHOVER_USER_KEY=${PO_USER_SECRET}:latest"
  fi
fi

EXTRA_ENV=""
[[ -n "${PUSHOVER_DEVICE:-}" ]] && EXTRA_ENV+=",PUSHOVER_DEVICE=${PUSHOVER_DEVICE}"
[[ -n "${TWILIO_ACCOUNT_SID:-}" ]] && EXTRA_ENV+=",TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}"
[[ -n "${TWILIO_AUTH_TOKEN:-}" ]] && EXTRA_ENV+=",TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}"
[[ -n "${TWILIO_FROM_NUMBER:-}" ]] && EXTRA_ENV+=",TWILIO_FROM_NUMBER=${TWILIO_FROM_NUMBER}"
[[ -n "${TWILIO_TO_NUMBER:-}" ]] && EXTRA_ENV+=",TWILIO_TO_NUMBER=${TWILIO_TO_NUMBER}"
[[ -n "${TWILIO_MODE:-}" ]] && EXTRA_ENV+=",TWILIO_MODE=${TWILIO_MODE}"

DEPLOY_ARGS=(
  --project="${GCP_PROJECT_ID}"
  --region="${GCP_REGION}"
  --image="${IMAGE}"
  --platform=managed
  --min-instances=0
  --max-instances=5
  --port=8080
  --set-env-vars="${ENV_VARS}${EXTRA_ENV}"
  --allow-unauthenticated
)

if [[ -n "${SECRETS}" ]]; then
  DEPLOY_ARGS+=(--set-secrets="${SECRETS}")
fi

echo "==> Deploying Cloud Run service ${SERVICE_NAME}"
"${GCLOUD}" run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

echo "Deploy complete."
