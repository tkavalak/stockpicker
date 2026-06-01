#!/usr/bin/env bash
# Run rule-engine with service venv + GCP credentials.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${DIR}/../.." && pwd)"
# shellcheck source=../../scripts/gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

gcp_check_auth || exit 1

cd "${DIR}"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

export PYTHONPATH="${DIR}/src"
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-stockadvisor-498000}"

# Cloud Run sets PORT=8080. Locally, fall back if 8080 is taken (stale run / polygon-streamer).
if [[ -z "${PORT:-}" ]]; then
  if command -v lsof >/dev/null 2>&1 && lsof -i :8080 -sTCP:LISTEN >/dev/null 2>&1; then
    export PORT=8081
    echo "Port 8080 in use; admin HTTP will listen on :8081 (override with PORT=...)" >&2
  else
    export PORT=8080
  fi
fi

exec .venv/bin/python -m rule_engine.main "$@"
