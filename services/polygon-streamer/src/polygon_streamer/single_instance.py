"""Ensure at most one polygon-streamer process holds the Polygon WebSocket."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO


class SingleInstanceError(RuntimeError):
    """Raised when another streamer already holds the process lock."""


def default_lock_path() -> Path:
    override = os.environ.get("POLYGON_STREAMER_LOCK", "").strip()
    if override:
        return Path(override)
    return Path("/tmp/polygon-streamer.lock")


class single_instance:
    """Non-blocking file lock — one streamer process per machine/API key."""

    def __init__(self, lock_path: Path | str | None = None) -> None:
        self._path = Path(lock_path) if lock_path else default_lock_path()
        self._fp: TextIO | None = None

    def __enter__(self) -> single_instance:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self._path.open("w", encoding="utf-8")
        try:
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._fp.close()
            self._fp = None
            raise SingleInstanceError(
                f"Another polygon-streamer is already running (lock: {self._path}). "
                "Polygon allows one WebSocket per API key — run "
                "./scripts/stop-pipeline.sh before starting again."
            ) from exc
        self._fp.write(str(os.getpid()))
        self._fp.flush()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fp is not None:
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
            self._fp.close()
            self._fp = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass
