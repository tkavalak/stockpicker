#!/usr/bin/env bash
# Run notification-service with service venv + GCP credentials.
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
export PUBSUB_SUBSCRIPTION_NOTIFICATION="${PUBSUB_SUBSCRIPTION_NOTIFICATION:-notification-alert-decisions}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

# Pick a free admin port (8080 often taken by polygon-streamer / rule-engine).
if [[ -z "${PORT:-}" ]]; then
  for try_port in 8083 8084 8085 8080 8081 8082; do
    if ! command -v lsof >/dev/null 2>&1 || ! lsof -i :"${try_port}" -sTCP:LISTEN >/dev/null 2>&1; then
      export PORT="${try_port}"
      break
    fi
  done
  export PORT="${PORT:-8083}"
  echo "Admin HTTP listening on :${PORT}" >&2
fi

exec .venv/bin/python -m notification_service.main "$@"
