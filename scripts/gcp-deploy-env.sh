# Source after setting REPO_ROOT in deploy scripts.
# Defines GCLOUD (absolute path to repo-bundled gcloud).

if [[ -z "${REPO_ROOT:-}" ]]; then
  echo "ERROR: set REPO_ROOT before sourcing scripts/gcp-deploy-env.sh" >&2
  return 1 2>/dev/null || exit 1
fi

# shellcheck source=gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

if ! gcp_check_auth; then
  return 1 2>/dev/null || exit 1
fi

GCLOUD="$(command -v gcloud)"
export GCLOUD

if [[ ! -x "${GCLOUD}" ]]; then
  echo "ERROR: gcloud not found. Expected: ${REPO_ROOT}/.tools/google-cloud-sdk/bin/gcloud" >&2
  return 1 2>/dev/null || exit 1
fi

# Grant Secret Manager access to the default Cloud Run runtime service account.
grant_secret_accessor() {
  local secret_id="$1"
  : "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
  local project_number
  project_number="$("${GCLOUD}" projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)')"
  local member="serviceAccount:${project_number}-compute@developer.gserviceaccount.com"
  echo "==> Granting secretAccessor on ${secret_id} to ${member}"
  "${GCLOUD}" secrets add-iam-policy-binding "${secret_id}" \
    --project="${GCP_PROJECT_ID}" \
    --member="${member}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null 2>&1 || true
}
