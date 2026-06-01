#!/usr/bin/env bash
# Run terraform with repo-local binary and GCP credentials.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=../../scripts/gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

if ! command -v terraform >/dev/null 2>&1; then
  echo "ERROR: terraform not found in ${REPO_ROOT}/.tools/" >&2
  exit 127
fi

gcp_check_auth || exit 1

cd "${REPO_ROOT}/infra/terraform"
exec terraform "$@"
