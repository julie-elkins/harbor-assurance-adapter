"""Project a Harbor receipt into the harness's metadata-only ATIF contract.

Design rules:

1. Read a validated receipt only; never read a trajectory or provider output.
2. Preserve missing and invalid evidence as blocked metadata, never as a pass.
3. Prefix the stored digest only when it is a valid SHA-256 value.
4. Use an explicit unavailable schema marker rather than inventing a supported
   ATIF version.
"""

from __future__ import annotations

import re
from typing import Final

from .models import RunReceipt


METADATA_ONLY_REDACTION_POLICY: Final = "metadata-only-v1"
_OBSERVED_BENCHMARK_OUTCOMES = frozenset({"passed", "failed", "partial"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _artifact_status(receipt: RunReceipt, digest: str | None) -> str:
    if receipt.atif_scan_status == "passed" and digest is not None:
        return "observed"
    if receipt.atif_scan_status == "invalid":
        return "invalid"
    return "missing"


def _terminal_status(receipt: RunReceipt) -> str:
    if receipt.status == "completed":
        return "completed"
    if receipt.timed_out:
        return "timed_out"
    if receipt.status == "refused":
        return "refused"
    return "missing"


def _digest(value: str | None) -> str | None:
    if value is None or _SHA256.fullmatch(value) is None:
        return None
    return f"sha256:{value}"


def receipt_to_evidence_summary(receipt: RunReceipt) -> dict[str, object]:
    """Return only the fields accepted by the harness conformance check."""

    trajectory_digest = _digest(receipt.trajectory_digest)
    artifact_status = _artifact_status(receipt, trajectory_digest)
    observed = artifact_status == "observed"
    semantic_outcome = (
        receipt.benchmark_status
        if receipt.benchmark_status in _OBSERVED_BENCHMARK_OUTCOMES
        else None
    )
    return {
        "source_id": "harbor",
        "run_id": receipt.run_id,
        "schema_version": receipt.atif_schema_version or "ATIF-unavailable",
        "trajectory_digest": trajectory_digest if observed else None,
        "step_count": (
            receipt.atif_step_count
            if observed and receipt.atif_step_count is not None
            else 0
        ),
        "tool_call_count": (
            receipt.atif_tool_call_count
            if observed and receipt.atif_tool_call_count is not None
            else 0
        ),
        "terminal_status": _terminal_status(receipt),
        "artifact_status": artifact_status,
        "artifact_count": 1 if observed else 0,
        "redaction_policy": METADATA_ONLY_REDACTION_POLICY,
        "event_linkage_status": "complete" if observed else "missing",
        "semantic_outcome": semantic_outcome,
    }
