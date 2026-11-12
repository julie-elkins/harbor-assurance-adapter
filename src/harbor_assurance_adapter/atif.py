"""Metadata-only checks for the local ATIF trajectory artifact.

Design rules:

1. Read the local trajectory only after Harbor has created it.
2. Inspect schema shape and bounded counts, never trajectory content.
3. Hash the artifact so a later review can identify which local record was scanned.
4. Treat a missing or malformed artifact as unavailable, never as clean.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_SCHEMA_VERSIONS = frozenset({"ATIF-v1.2", "ATIF-v1.5"})


@dataclass(frozen=True)
class AtifScanResult:
    """Metadata-only outcome of one local ATIF scan."""

    status: str
    assurance_status: str
    trajectory_digest: str | None = None
    step_count: int | None = None
    tool_call_count: int | None = None
    schema_version: str | None = None


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _invalid(digest: str | None) -> AtifScanResult:
    return AtifScanResult(
        status="invalid",
        assurance_status="metadata-refused",
        trajectory_digest=digest,
    )


def scan_trajectory(path: Path | None) -> AtifScanResult:
    """Check ATIF structure without returning any trajectory content."""

    if path is None or not path.is_file():
        return AtifScanResult(
            status="missing",
            assurance_status="metadata-unavailable",
        )
    try:
        raw = path.read_bytes()
        data: Any = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _invalid(None)

    digest = _digest(raw)
    if (
        not isinstance(data, dict)
        or data.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS
    ):
        return _invalid(digest)
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        return _invalid(digest)

    tool_call_count = 0
    for step in steps:
        if not isinstance(step, dict):
            return _invalid(digest)
        tool_calls = step.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            return _invalid(digest)
        tool_call_count += len(tool_calls)

    return AtifScanResult(
        status="passed",
        assurance_status="metadata-checked",
        trajectory_digest=digest,
        step_count=len(steps),
        tool_call_count=tool_call_count,
        schema_version=data["schema_version"],
    )


def latest_trajectory(root: Path, started_epoch: float) -> Path | None:
    """Find the newest ATIF trajectory written by the current Harbor run."""

    candidates = [
        path
        for path in root.glob("*/*/agent/trajectory.json")
        if path.is_file() and path.stat().st_mtime >= started_epoch - 1.0
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None
