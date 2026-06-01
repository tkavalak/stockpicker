#!/usr/bin/env bash
# Stop local pipeline services started by run-pipeline.sh.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${REPO_ROOT}/.logs/pipeline"

for port in 8080 8084 8081 8082 8083; do
  pids="$(lsof -ti :"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    echo "Stopping :${port} (${pids})"
    kill ${pids} 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti :"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
      kill -9 ${pids} 2>/dev/null || true
    fi
  fi
done

pkill -f "polygon_streamer.main" 2>/dev/null || true
pkill -f "polygon_ws_poc.py" 2>/dev/null || true
rm -f "${LOG_DIR}/polygon-streamer.lock" 2>/dev/null || true

if [[ -d "${LOG_DIR}" ]]; then
  rm -f "${LOG_DIR}"/*.pid 2>/dev/null || true
fi

echo "Pipeline stopped."
