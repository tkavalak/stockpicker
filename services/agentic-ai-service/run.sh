#!/usr/bin/env bash
# Run agentic-ai-service locally with service venv + GCP credentials.
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
export PUBSUB_SUBSCRIPTION_AGENTIC_AI="${PUBSUB_SUBSCRIPTION_AGENTIC_AI:-agentic-ai-trigger-events}"
export PUBSUB_TOPIC_ALERT_DECISIONS="${PUBSUB_TOPIC_ALERT_DECISIONS:-alert-decisions}"
export FIRESTORE_COLLECTION_AGENT_STATE="${FIRESTORE_COLLECTION_AGENT_STATE:-agent_state}"
export MAX_CONCURRENT_WORKFLOWS="${MAX_CONCURRENT_WORKFLOWS:-5}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +a
fi

if [[ -z "${PORT:-}" ]]; then
  if command -v lsof >/dev/null 2>&1 && lsof -i :8080 -sTCP:LISTEN >/dev/null 2>&1; then
    export PORT=8082
    echo "Port 8080 in use; admin HTTP will listen on :8082" >&2
  else
    export PORT=8080
  fi
fi

exec .venv/bin/python -m agentic_ai.main "$@"
