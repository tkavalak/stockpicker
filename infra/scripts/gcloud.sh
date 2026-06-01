#!/usr/bin/env bash
# Run gcloud with repo-local SDK and credentials (no global install needed).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"
gcp_check_auth || exit 1
exec gcloud "$@"
