#!/usr/bin/env bash
# Configure Firestore + Pushover with repo GCP credentials loaded.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"
gcp_check_auth || exit 1
exec python3 "${REPO_ROOT}/scripts/configure-business-run.py" "$@"
