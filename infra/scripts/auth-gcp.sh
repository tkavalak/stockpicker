#!/usr/bin/env bash
# Authenticate gcloud for WO-4 provisioning (stores config in repo .gcloud/).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../scripts/gcp-env.sh
source "${REPO_ROOT}/scripts/gcp-env.sh"

PROJECT_ID="${GCP_PROJECT_ID:-stockadvisor-498000}"

mkdir -p "${CLOUDSDK_CONFIG}"

echo "Config directory: ${CLOUDSDK_CONFIG}"
echo "Project: ${PROJECT_ID}"
echo ""
echo "Opening browser for gcloud login..."
gcloud auth login --project="${PROJECT_ID}"
gcloud auth application-default login --project="${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}"

echo ""
echo "GCP auth complete. Run: GCP_PROJECT_ID=${PROJECT_ID} ./infra/scripts/provision.sh -auto-approve"
