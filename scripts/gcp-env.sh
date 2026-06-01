# Source this file:  source scripts/gcp-env.sh
# Sets PATH for terraform/gcloud and Application Default Credentials.
# Safe to source multiple times — PATH and ADC are refreshed each time.

_GCP_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CLOUDSDK_CONFIG="${_GCP_REPO_ROOT}/.gcloud"
export PATH="${_GCP_REPO_ROOT}/.tools:${_GCP_REPO_ROOT}/.tools/google-cloud-sdk/bin:${PATH}"

if [[ -f "${CLOUDSDK_CONFIG}/application_default_credentials.json" ]]; then
  export GOOGLE_APPLICATION_CREDENTIALS="${CLOUDSDK_CONFIG}/application_default_credentials.json"
fi

if [[ -z "${GCP_PROJECT_ID:-}" ]] && [[ -f "${_GCP_REPO_ROOT}/infra/terraform/terraform.tfvars" ]]; then
  GCP_PROJECT_ID="$(grep -E '^project_id' "${_GCP_REPO_ROOT}/infra/terraform/terraform.tfvars" | sed 's/.*= *"\(.*\)".*/\1/')"
  export GCP_PROJECT_ID
fi

if [[ -n "${_GCP_ENV_LOADED:-}" ]]; then
  return 0 2>/dev/null || true
fi
_GCP_ENV_LOADED=1

gcp_check_auth() {
  if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]] || [[ ! -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
    echo "ERROR: GCP credentials not found." >&2
    echo "Run once from repo root:" >&2
    echo "  source scripts/gcp-env.sh && ./infra/scripts/auth-gcp.sh" >&2
    return 1
  fi
  if ! command -v gcloud >/dev/null 2>&1; then
    echo "ERROR: gcloud not found under ${_GCP_REPO_ROOT}/.tools/google-cloud-sdk" >&2
    return 1
  fi
  return 0
}
