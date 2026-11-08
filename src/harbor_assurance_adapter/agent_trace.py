"""Metadata-only summaries of local agent event logs.

Design rules:

1. Read local event logs only after Harbor has created them.
2. Inspect event types, bounded counts, and terminal state only; never export content.
3. Hash the local log so a later review can identify which evidence was scanned.
4. Treat malformed or empty logs as unavailable, not as a clean run.
5. Keep the summary generic so Codex and other JSONL-producing agents share one
   contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


_TERMINAL_EVENTS = frozenset(
    {"turn.completed", "turn.failed", "turn.cancelled", "error", "result"}
)


def _label(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.replace("_", "-")


@dataclass(frozen=True)
class AgentTraceSummary:
    """Public-safe facts from one local JSONL agent event log."""

    status: str
    event_count: int | None = None
    tool_call_count: int | None = None
    log_digest: str | None = None
    last_event_type: str | None = None
    last_item_type: str | None = None
    last_status: str | None = None
    terminal_event_type: str | None = None


def _scan(path: Path) -> AgentTraceSummary:
    try:
        raw = path.read_bytes()
    except OSError:
        return AgentTraceSummary(status="metadata-unavailable")

    digest = hashlib.sha256(raw).hexdigest()
    event_count = 0
    tool_call_count = 0
    last_event_type: str | None = None
    last_item_type: str | None = None
    last_status: str | None = None
    terminal_event_type: str | None = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return AgentTraceSummary(
                status="metadata-invalid",
                log_digest=digest,
            )
        if not isinstance(event, dict):
            return AgentTraceSummary(
                status="metadata-invalid",
                log_digest=digest,
            )
        event_count += 1
        event_type = _label(event.get("type"))
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                tool_call_count += sum(
                    isinstance(block, dict) and block.get("type") == "tool_use"
                    for block in content
                )
        item = event.get("item")
        if isinstance(item, dict):
            item_type = _label(item.get("type"))
            item_status = _label(item.get("status"))
            if item_type is not None:
                last_item_type = item_type
            if item_status is not None:
                last_status = item_status
            if item.get("exit_code") is not None:
                last_status = _label(item.get("status")) or last_status
        top_level_status = _label(event.get("status"))
        if top_level_status is not None:
            last_status = top_level_status
        if event_type is not None:
            last_event_type = event_type
            if event_type in _TERMINAL_EVENTS:
                terminal_event_type = event_type
    if event_count == 0:
        return AgentTraceSummary(
            status="metadata-invalid",
            log_digest=digest,
        )

    return AgentTraceSummary(
        status="metadata-checked",
        event_count=event_count,
        tool_call_count=tool_call_count,
        log_digest=digest,
        last_event_type=last_event_type,
        last_item_type=last_item_type,
        last_status=last_status,
        terminal_event_type=terminal_event_type,
    )


def latest_agent_trace(root: Path, started_epoch: float) -> AgentTraceSummary:
    """Summarize the newest JSONL agent log written by the current run."""

    candidates = [
        path
        for path in root.rglob("agent/*.txt")
        if path.is_file() and path.stat().st_mtime >= started_epoch - 1.0
    ]
    if not candidates:
        return AgentTraceSummary(status="metadata-unavailable")
    return _scan(max(candidates, key=lambda path: path.stat().st_mtime))
