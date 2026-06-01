#!/usr/bin/env bash
# Remove Stock Picker Cloud Run services (keeps Pub/Sub, Firestore, secrets, Terraform).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env}"
export GCP_REGION="${GCP_REGION:-us-central1}"

SERVICES=(
  polygon-websocket-streamer
  market-event-processor
  rule-engine
  agentic-ai-service
  notification-service
)

echo "Using gcloud: ${GCLOUD}"
echo "Project: ${GCP_PROJECT_ID}  Region: ${GCP_REGION}"
echo ""
echo "This deletes Cloud Run services only (not Pub/Sub, Firestore, or secrets)."
echo ""

for svc in "${SERVICES[@]}"; do
  if "${GCLOUD}" run services describe "${svc}" \
    --project="${GCP_PROJECT_ID}" \
    --region="${GCP_REGION}" \
    --quiet >/dev/null 2>&1; then
    echo "==> Deleting ${svc}"
    "${GCLOUD}" run services delete "${svc}" \
      --project="${GCP_PROJECT_ID}" \
      --region="${GCP_REGION}" \
      --quiet
  else
    echo "==> Skipping ${svc} (not deployed)"
  fi
done

echo ""
echo "Remaining Cloud Run services:"
"${GCLOUD}" run services list --project="${GCP_PROJECT_ID}" --region="${GCP_REGION}" 2>/dev/null || true
echo ""
echo "Undeploy complete. Run locally: ${REPO_ROOT}/scripts/run-pipeline.sh"
echo "Redeploy later: ${REPO_ROOT}/scripts/deploy-to-gcloud.sh"
