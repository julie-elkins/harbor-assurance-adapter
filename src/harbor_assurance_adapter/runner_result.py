"""Metadata-only interpretation of a Harbor job result."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent_trace import latest_agent_trace


@dataclass(frozen=True)
class RunnerResult:
    """Public-safe Harbor outcome fields."""

    status: str
    total_trials: int | None = None
    completed_trials: int | None = None
    errored_trials: int | None = None
    observed_cost_usd: float | None = None
    benchmark_status: str = "not-run"
    benchmark_score: float | None = None
    benchmark_failure_kind: str | None = None
    benchmark_failure_phase: str | None = None
    failure_kind: str | None = None
    failure_phase: str | None = None
    failure_breakdown: dict[str, int] | None = None

    @property
    def successful_trials(self) -> int | None:
        """Count completed trials that did not also error."""

        if self.completed_trials is None or self.errored_trials is None:
            return None
        return max(0, self.completed_trials - self.errored_trials)

    @property
    def clean(self) -> bool:
        return (
            self.status == "completed"
            and self.total_trials is not None
            and self.total_trials > 0
            and self.completed_trials == self.total_trials
            and self.errored_trials == 0
        )


def _non_negative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _non_negative_number(value: Any) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        else None
    )


def _benchmark_observation(stats: dict[str, Any]) -> tuple[str, float | None]:
    """Interpret the single configured Terminal-Bench aggregate metric."""

    evals = stats.get("evals")
    if not isinstance(evals, dict) or len(evals) != 1:
        return "unknown", None
    evaluation = next(iter(evals.values()))
    if not isinstance(evaluation, dict):
        return "unknown", None
    metrics = evaluation.get("metrics")
    if not isinstance(metrics, list) or len(metrics) != 1:
        return "unknown", None
    metric = metrics[0]
    if not isinstance(metric, dict):
        return "unknown", None
    score = _non_negative_number(metric.get("mean"))
    if score is None:
        return "unknown", None
    if score == 1.0:
        return "passed", score
    if score == 0.0:
        return "failed", score
    return "partial", score


def _verifier_failure_observation(
    result_root: Path,
) -> tuple[str | None, str | None]:
    """Classify verifier setup failures without exporting verifier output."""

    for path in result_root.glob("*/verifier/test-stdout.txt"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        normalized = re.sub(r"\s+", " ", text.lower())
        if (
            "failed to download" in normalized
            and "uv" in normalized
        ) or "uvx: command not found" in normalized:
            return "VerifierEnvironmentFailure", "verifier-setup"
        if "/root/.local/bin/env: no such file or directory" in normalized:
            return "VerifierEnvironmentFailure", "verifier-setup"
    return None, None


def _has_provider_quota_marker(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    return any(
        marker in normalized
        for marker in (
            "usage limit",
            "rate limit",
            "quota",
            "billing limit",
        )
    )


def _trace_is_incomplete(trial_root: Path) -> bool:
    """Detect an agent log that ends before a terminal event."""

    trace = latest_agent_trace(trial_root, 0.0)
    return (
        trace.status == "metadata-checked"
        and trace.terminal_event_type is None
        and trace.last_status == "in-progress"
    )


def _trial_failure_breakdown(
    exception_maps: list[dict[str, Any]],
    result_root: Path,
) -> dict[str, int]:
    """Count evidenced failure categories without retaining raw diagnostics.

    Counts are evidence counts, not disjoint task counts: one trial can expose
    both a provider refusal and a timeout while the runner is unwinding it.
    """

    trial_kinds: dict[str, set[str]] = {}
    for mapping in exception_maps:
        for kind, names in mapping.items():
            if not isinstance(kind, str) or not isinstance(names, list):
                continue
            for trial_name in names:
                if isinstance(trial_name, str) and trial_name:
                    trial_kinds.setdefault(trial_name, set()).add(kind)

    breakdown: dict[str, int] = {}
    for trial_name, kinds in trial_kinds.items():
        trial_root = result_root / trial_name
        trial_result: dict[str, Any] = {}
        try:
            loaded = json.loads(
                (trial_root / "result.json").read_text(encoding="utf-8")
            )
            if isinstance(loaded, dict):
                trial_result = loaded
        except (OSError, ValueError, TypeError):
            pass

        message_parts: list[str] = []
        exception_info = trial_result.get("exception_info")
        if isinstance(exception_info, dict):
            message_parts.extend(
                value.lower()
                for key in ("exception_message", "exception_traceback")
                if isinstance(value := exception_info.get(key), str)
            )
        for agent_log_path in trial_root.glob("agent/*"):
            try:
                message_parts.append(
                    agent_log_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    ).lower()
                )
            except (OSError, UnicodeError):
                continue
        message = " ".join(message_parts)

        categories: list[str] = []
        if _has_provider_quota_marker(message):
            categories.append("ProviderQuotaExceeded")
        if "AgentTimeoutError" in kinds:
            categories.append("AgentTimeoutError")
        if (
            trial_result
            and "agent_execution" in trial_result
            and (
                trial_result.get("agent_execution") is None
                or any(kind.startswith("AgentSetup") for kind in kinds)
            )
        ):
            categories.append("AgentSetupFailure")
        elif _trace_is_incomplete(trial_root):
            categories.append("AgentExecutionIncomplete")
        elif "NonZeroAgentExitCodeError" in kinds and not categories:
            categories.append("NonZeroAgentExitCodeError")
        if not categories:
            categories.append(sorted(kinds)[0])
        for category in categories:
            breakdown[category] = breakdown.get(category, 0) + 1

    if breakdown:
        return breakdown
    for kind in (
        kind
        for mapping in exception_maps
        for kind in mapping
        if isinstance(kind, str) and kind
    ):
        breakdown[kind] = breakdown.get(kind, 0) + 1
    return breakdown


def _failure_observation(
    stats: dict[str, Any],
    result_root: Path,
) -> tuple[str | None, str | None, dict[str, int] | None]:
    """Classify a Harbor error without retaining its message or raw output."""

    exception_stats = stats.get("exception_stats")
    exception_maps: list[dict[str, Any]] = []
    if isinstance(exception_stats, dict):
        exception_maps.append(exception_stats)
    evals = stats.get("evals")
    if isinstance(evals, dict):
        for evaluation in evals.values():
            if not isinstance(evaluation, dict):
                continue
            nested = evaluation.get("exception_stats")
            if isinstance(nested, dict):
                exception_maps.append(nested)
    kinds = sorted(
        kind
        for mapping in exception_maps
        for kind in mapping
        if isinstance(kind, str) and kind
    )
    if not kinds:
        return None, None, None
    failure_breakdown = _trial_failure_breakdown(exception_maps, result_root)
    if len(failure_breakdown) == 1:
        kind = next(iter(failure_breakdown))
    else:
        kind = "MixedFailures"
    if kind == "ProviderQuotaExceeded":
        phase = "provider"
    elif kind == "AgentTimeoutError":
        phase = "agent-timeout"
    elif kind == "AgentSetupFailure":
        phase = "agent-setup"
    elif kind == "AgentExecutionIncomplete":
        phase = "agent-execution"
    elif kind.startswith("Verifier"):
        phase = "verifier"
    elif kind == "MixedFailures":
        phase = "runner"
    else:
        phase = "agent-execution"
    return kind, phase, failure_breakdown


def _parse(path: Path) -> RunnerResult:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stats = data["stats"]
        if not isinstance(stats, dict):
            return RunnerResult(status="invalid")
        total_trials = _non_negative_int(data.get("n_total_trials"))
        completed_trials = _non_negative_int(stats.get("n_completed_trials"))
        errored_trials = _non_negative_int(stats.get("n_errored_trials"))
        observed_cost_usd = _non_negative_number(stats.get("cost_usd"))
    except (OSError, ValueError, TypeError, KeyError):
        return RunnerResult(status="invalid")

    if total_trials is None or completed_trials is None or errored_trials is None:
        return RunnerResult(status="invalid")
    status = "completed" if errored_trials == 0 and completed_trials == total_trials else "errored"
    failure_kind, failure_phase, failure_breakdown = (
        _failure_observation(stats, path.parent)
        if status == "errored"
        else (None, None, None)
    )
    benchmark_status, benchmark_score = (
        _benchmark_observation(stats) if status == "completed" else ("not-run", None)
    )
    benchmark_failure_kind, benchmark_failure_phase = (
        _verifier_failure_observation(path.parent)
        if status == "completed"
        else (None, None)
    )
    if benchmark_failure_kind is not None:
        benchmark_status = "invalid"
        benchmark_score = None
    return RunnerResult(
        status=status,
        total_trials=total_trials,
        completed_trials=completed_trials,
        errored_trials=errored_trials,
        observed_cost_usd=observed_cost_usd,
        benchmark_status=benchmark_status,
        benchmark_score=benchmark_score,
        benchmark_failure_kind=benchmark_failure_kind,
        benchmark_failure_phase=benchmark_failure_phase,
        failure_kind=failure_kind,
        failure_phase=failure_phase,
        failure_breakdown=failure_breakdown,
    )


def latest_result(root: Path, started_epoch: float) -> RunnerResult:
    """Read only the newest result written by the current invocation."""

    candidates = [
        path
        for path in root.glob("*/result.json")
        if path.is_file() and path.stat().st_mtime >= started_epoch - 1.0
    ]
    if not candidates:
        return RunnerResult(status="missing")
    return _parse(max(candidates, key=lambda path: path.stat().st_mtime))


def now_epoch() -> float:
    """Keep the wall-clock dependency in one testable function."""

    return time.time()
