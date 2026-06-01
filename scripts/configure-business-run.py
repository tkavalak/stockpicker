#!/usr/bin/env python3
"""Seed Firestore and enable Pushover channel from repo .env for a business pipeline run."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "infra" / "scripts"))

from gcp_credentials import setup_repo_gcp_env  # noqa: E402

setup_repo_gcp_env(REPO_ROOT)

from google.cloud import firestore  # noqa: E402

from seed_firestore import (  # noqa: E402
    ensure_collection_placeholders,
    seed_notification_config,
    seed_rule_configs,
)


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _disconnected_channel() -> dict:
    return {
        "status": "disconnected",
        "enabled": False,
        "consecutive_failures": 0,
        "last_verified_at": None,
        "routing_rule": None,
        "credentials": {},
    }


def enable_pushover_channel(client: firestore.Client) -> None:
    app_token = os.environ.get("PUSHOVER_APP_TOKEN", "").strip()
    user_key = os.environ.get("PUSHOVER_USER_KEY", "").strip()
    if not app_token or not user_key:
        print(
            "WARN: Set PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY in .env to enable Pushover"
        )
        return

    doc_ref = client.collection("notification_configs").document("default")
    doc = doc_ref.get()
    data = doc.to_dict() if doc.exists else {}
    channels = dict(data.get("channels") or {})

    creds: dict[str, str] = {"user_key": user_key}
    device = os.environ.get("PUSHOVER_DEVICE", "").strip()
    if device:
        creds["device"] = device

    channels["pushover"] = {
        "status": "connected",
        "enabled": True,
        "consecutive_failures": 0,
        "last_verified_at": None,
        "routing_rule": None,
        "credentials": creds,
    }
    # Disable email when using Pushover for alerts.
    channels["email"] = _disconnected_channel()

    doc_ref.set({"channels": channels}, merge=True)
    print("enabled pushover channel (email disabled)")


def main() -> None:
    _load_dotenv()
    project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise SystemExit("Set GCP_PROJECT_ID in .env")

    client = firestore.Client(project=project)
    seed_rule_configs(client, overwrite=False)
    seed_notification_config(client, overwrite=False)
    ensure_collection_placeholders(client)
    enable_pushover_channel(client)
    print("Business run configuration complete.")


if __name__ == "__main__":
    main()
