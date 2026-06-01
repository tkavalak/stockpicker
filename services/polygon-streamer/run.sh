#!/usr/bin/env bash
# Run polygon-streamer with service venv + GCP credentials.
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

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${REPO_ROOT}/.env"
  set +a
fi

exec .venv/bin/python -m polygon_streamer.main "$@"
