#!/usr/bin/env python3
"""Seed default rule_configs documents after WO-4 Firestore provisioning."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google.cloud import firestore

DEFAULT_RULES = [
    {
        "rule_name": "PRICE_SPIKE_5M",
        "enabled": True,
        "threshold": 0.5,
        "symbols": ["*"],
    },
]

REMOVED_RULE_IDS = ("VOLUME_SPIKE",)


def seed_rule_configs(
    client: firestore.Client,
    *,
    overwrite: bool = False,
) -> None:
    collection = client.collection("rule_configs")
    for rule in DEFAULT_RULES:
        doc_id = rule["rule_name"]
        doc_ref = collection.document(doc_id)
        if doc_ref.get().exists and not overwrite:
            print(f"skip rule_configs/{doc_id} (already exists)")
            continue
        doc_ref.set(rule)
        print(f"seeded rule_configs/{doc_id}")
    for doc_id in REMOVED_RULE_IDS:
        doc_ref = collection.document(doc_id)
        if doc_ref.get().exists:
            doc_ref.delete()
            print(f"deleted rule_configs/{doc_id}")


# Channel map (WO-13). Secrets remain in env / Secret Manager; credentials filled via API.
DEFAULT_NOTIFICATION_CONFIG = {
    "channels": {
        "email": {
            "status": "disconnected",
            "enabled": False,
            "consecutive_failures": 0,
            "credentials": {},
            "routing_rule": None,
        },
        "slack": {
            "status": "disconnected",
            "enabled": False,
            "consecutive_failures": 0,
            "credentials": {},
            "routing_rule": None,
        },
        "teams": {
            "status": "disconnected",
            "enabled": False,
            "consecutive_failures": 0,
            "credentials": {},
            "routing_rule": None,
        },
        "twilio": {
            "status": "disconnected",
            "enabled": False,
            "consecutive_failures": 0,
            "credentials": {},
            "routing_rule": None,
        },
        "pushover": {
            "status": "disconnected",
            "enabled": False,
            "consecutive_failures": 0,
            "credentials": {},
            "routing_rule": None,
        },
    },
}


def seed_notification_config(
    client: firestore.Client,
    *,
    overwrite: bool = False,
) -> None:
    doc_ref = client.collection("notification_configs").document("default")
    if doc_ref.get().exists and not overwrite:
        print("skip notification_configs/default (already exists)")
        return
    doc_ref.set(DEFAULT_NOTIFICATION_CONFIG)
    print("seeded notification_configs/default")


def ensure_collection_placeholders(client: firestore.Client) -> None:
    """Firestore creates collections on first write; add placeholder docs for empty collections."""
    doc_ref = client.collection("agent_state").document("_schema")
    if doc_ref.get().exists:
        print("skip agent_state/_schema (already exists)")
        return
    doc_ref.set(
        {
            "_placeholder": True,
            "description": "Collection initialized by WO-4 provisioning",
        }
    )
    print("initialized agent_state/_schema")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    scripts_dir = repo_root / "scripts"
    if scripts_dir.is_dir() and str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from gcp_credentials import setup_repo_gcp_env

        setup_repo_gcp_env(repo_root)
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Seed Firestore collections for Stock Picker")
    parser.add_argument(
        "--project",
        default=os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        help="GCP project ID",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing rule_configs documents",
    )
    args = parser.parse_args()

    if not args.project:
        raise SystemExit("Set --project or GCP_PROJECT_ID / GOOGLE_CLOUD_PROJECT")

    client = firestore.Client(project=args.project)
    seed_rule_configs(client, overwrite=args.overwrite)
    seed_notification_config(client, overwrite=args.overwrite)
    ensure_collection_placeholders(client)
    print("Firestore seed complete")


if __name__ == "__main__":
    main()
