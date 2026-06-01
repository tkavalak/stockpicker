#!/usr/bin/env bash
# Quick checks for common terminal/setup errors.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${REPO_ROOT}"
# shellcheck source=gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

ok() { echo "  OK  $*"; }
fail() { echo "  FAIL $*"; }

echo "Stock Picker doctor (${REPO_ROOT})"
echo ""

if [[ -f .env ]]; then ok ".env exists"; else fail "missing .env — copy .env.example"; fi
if [[ -f "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then ok "GCP ADC"; else fail "run: ./infra/scripts/auth-gcp.sh"; fi
if command -v gcloud >/dev/null 2>&1; then ok "gcloud -> $(command -v gcloud)"; else fail "gcloud not on PATH — source scripts/gcp-env.sh"; fi
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then ok "GCP_PROJECT_ID=${GCP_PROJECT_ID}"; else fail "set GCP_PROJECT_ID in .env"; fi

for var in PUSHOVER_APP_TOKEN PUSHOVER_USER_KEY POLYGON_API_KEY; do
  if [[ -n "${!var:-}" ]]; then ok "${var} set"; else fail "${var} missing in environment (add to .env)"; fi
done

echo ""
echo "Use ./infra/scripts/gcloud.sh instead of bare gcloud if PATH issues persist."
echo "Use ./scripts/run-pipeline.sh to run services (not python on individual .py files)."
