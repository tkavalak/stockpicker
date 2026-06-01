"""Point Google client libraries at this repo's .gcloud ADC (no global gcloud config)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def setup_repo_gcp_env(repo_root: Path | None = None) -> Path:
    """
    Set CLOUDSDK_CONFIG and GOOGLE_APPLICATION_CREDENTIALS for local tooling.

    Returns path to ADC file. Raises SystemExit if credentials are missing.
    """
    root = repo_root or REPO_ROOT
    cloudsdk = root / ".gcloud"
    adc = cloudsdk / "application_default_credentials.json"

    os.environ["CLOUDSDK_CONFIG"] = str(cloudsdk)
    tools_bin = root / ".tools" / "google-cloud-sdk" / "bin"
    if tools_bin.is_dir():
        path = os.environ.get("PATH", "")
        if str(tools_bin) not in path.split(os.pathsep):
            os.environ["PATH"] = f"{tools_bin}{os.pathsep}{path}"

    if not adc.is_file():
        raise SystemExit(
            "GCP Application Default Credentials not found.\n"
            f"  Expected: {adc}\n"
            "  Run from repo root:\n"
            "    source scripts/gcp-env.sh && ./infra/scripts/auth-gcp.sh"
        )

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc)
    return adc
