#!/usr/bin/env bash
# Grant Cloud Run's default runtime SA access to Secret Manager (fixes deploy Permission denied).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export REPO_ROOT
# shellcheck source=gcp-deploy-env.sh
source "${REPO_ROOT}/scripts/gcp-deploy-env.sh"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"

PROJECT_NUMBER="$("${GCLOUD}" projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Granting roles/secretmanager.secretAccessor to ${RUNTIME_SA}"
"${GCLOUD}" projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet >/dev/null

echo "Done. Redeploy Cloud Run services that use --set-secrets."
