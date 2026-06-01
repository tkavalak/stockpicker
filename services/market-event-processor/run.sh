#!/usr/bin/env bash
# Run market-event-processor with service venv + GCP credentials.
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
export PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR="${PUBSUB_SUBSCRIPTION_MARKET_EVENT_PROCESSOR:-market-event-processor-raw-market-events}"
export PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS="${PUBSUB_TOPIC_ENRICHED_MARKET_EVENTS:-enriched-market-events}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

# Local dev: in-memory windows unless REDIS_HOST is set (Memorystore in prod).
if [[ -z "${REDIS_HOST:-}" ]]; then
  export REDIS_USE_MEMORY="${REDIS_USE_MEMORY:-1}"
fi

if [[ -z "${PORT:-}" ]]; then
  for try_port in 8084 8085 8086 8080 8081 8082 8083; do
    if ! command -v lsof >/dev/null 2>&1 || ! lsof -i :"${try_port}" -sTCP:LISTEN >/dev/null 2>&1; then
      export PORT="${try_port}"
      break
    fi
  done
  export PORT="${PORT:-8084}"
  echo "Admin HTTP listening on :${PORT}" >&2
fi

exec .venv/bin/python -m market_event_processor.main "$@"
