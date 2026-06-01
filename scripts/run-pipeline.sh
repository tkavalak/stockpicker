#!/usr/bin/env bash
# Start the full Stock Picker business pipeline locally (5 services, fixed ports).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in .env}"

LOG_DIR="${REPO_ROOT}/.logs/pipeline"
mkdir -p "${LOG_DIR}"

# Fixed ports — one service each.
PORT_STREAMER=8080
PORT_MEP=8084
PORT_RULE_ENGINE=8081
PORT_AGENTIC=8082
PORT_NOTIFICATION=8083

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti :"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    return 0
  fi
  echo "Stopping process on :${port} (${pids})"
  kill ${pids} 2>/dev/null || true
  sleep 2
  pids="$(lsof -ti :"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    kill -9 ${pids} 2>/dev/null || true
    sleep 1
  fi
}

if [[ "${STOP_EXISTING:-1}" == "1" ]]; then
  # Polygon allows one WebSocket per API key — stop stray clients before bind.
  pkill -f "polygon_streamer.main" 2>/dev/null || true
  pkill -f "polygon_ws_poc.py" 2>/dev/null || true
  rm -f "${LOG_DIR}/polygon-streamer.lock" 2>/dev/null || true
  for p in "${PORT_STREAMER}" "${PORT_MEP}" "${PORT_RULE_ENGINE}" "${PORT_AGENTIC}" "${PORT_NOTIFICATION}"; do
    stop_port "${p}"
  done
fi

gcp_check_auth || exit 1

if [[ ! -f "${REPO_ROOT}/.env" ]]; then
  echo "ERROR: Missing ${REPO_ROOT}/.env — copy from .env.example" >&2
  exit 1
fi

echo "==> Configuring Firestore (rules + email channel)"
if [[ -f "${REPO_ROOT}/infra/scripts/requirements.txt" ]]; then
  python3 -m pip install -q -r "${REPO_ROOT}/infra/scripts/requirements.txt" 2>/dev/null || true
fi
"${REPO_ROOT}/scripts/configure-business-run.sh"

start_service() {
  local name="$1"
  local port="$2"
  local dir="$3"
  local log="${LOG_DIR}/${name}.log"
  echo "==> Starting ${name} on :${port} (log: ${log})"
  (
    cd "${dir}"
    export PORT="${port}"
    export GCP_PROJECT_ID
    if [[ -f "${REPO_ROOT}/.env" ]]; then
      set -a
      # shellcheck disable=SC1091
      source "${REPO_ROOT}/.env"
      set +a
    fi
    exec ./run.sh
  ) >>"${log}" 2>&1 &
  echo "${!}" >"${LOG_DIR}/${name}.pid"
}

start_service "polygon-streamer" "${PORT_STREAMER}" "${REPO_ROOT}/services/polygon-streamer"
start_service "market-event-processor" "${PORT_MEP}" "${REPO_ROOT}/services/market-event-processor"
start_service "rule-engine" "${PORT_RULE_ENGINE}" "${REPO_ROOT}/services/rule-engine"
start_service "agentic-ai" "${PORT_AGENTIC}" "${REPO_ROOT}/services/agentic-ai-service"
start_service "notification-service" "${PORT_NOTIFICATION}" "${REPO_ROOT}/services/notification-service"

echo ""
echo "Waiting for health endpoints (up to 45s)..."
deadline=$((SECONDS + 45))
all_ok=0
while (( SECONDS < deadline )); do
  all_ok=1
  for spec in \
    "${PORT_STREAMER}:streamer" \
    "${PORT_MEP}:mep" \
    "${PORT_RULE_ENGINE}:rule-engine" \
    "${PORT_AGENTIC}:agentic-ai" \
    "${PORT_NOTIFICATION}:notification"; do
    port="${spec%%:*}"
    name="${spec##*:}"
    if ! curl -sf "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      all_ok=0
      break
    fi
  done
  if [[ "${all_ok}" == "1" ]]; then
    break
  fi
  sleep 2
done

echo ""
echo "=== Health ==="
streamer_health="$(curl -sf "http://127.0.0.1:${PORT_STREAMER}/health" 2>/dev/null || echo '{}')"
if echo "${streamer_health}" | grep -q websocket; then
  echo "${streamer_health}"
else
  echo "streamer: DOWN or wrong process on :${PORT_STREAMER} — see ${LOG_DIR}/polygon-streamer.log"
  echo "${streamer_health}"
fi
echo ""
curl -s "http://127.0.0.1:${PORT_MEP}/health" || echo "mep: DOWN"
echo ""
curl -s "http://127.0.0.1:${PORT_RULE_ENGINE}/health" || echo "rule-engine: DOWN"
echo ""
curl -s "http://127.0.0.1:${PORT_AGENTIC}/health" || echo "agentic-ai: DOWN"
echo ""
curl -s "http://127.0.0.1:${PORT_NOTIFICATION}/health" || echo "notification: DOWN"
echo ""

echo "=== Pipeline running ==="
echo "  Polygon streamer     http://localhost:${PORT_STREAMER}/health"
echo "  Market event proc.   http://localhost:${PORT_MEP}/health"
echo "  Rule engine          http://localhost:${PORT_RULE_ENGINE}/health"
echo "  Agentic AI           http://localhost:${PORT_AGENTIC}/health"
echo "  Notification         http://localhost:${PORT_NOTIFICATION}/health"
echo ""
echo "Logs: ${LOG_DIR}/*.log"
echo "Stop:  ${REPO_ROOT}/scripts/stop-pipeline.sh"
echo ""
echo "Watch progress:"
echo "  tail -f ${LOG_DIR}/rule-engine.log"
echo "  tail -f ${LOG_DIR}/notification-service.log"
echo ""
echo "When rules fire you should see triggers in agentic-ai and Pushover notifications (set PUSHOVER_* in .env)."
echo "Requires market hours + Polygon WebSocket on your plan."
