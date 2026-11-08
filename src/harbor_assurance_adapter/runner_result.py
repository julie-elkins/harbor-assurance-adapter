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
    return "usage limit" in normalized or "rate limit" in normalized


def _trace_is_incomplete(trial_root: Path) -> bool:
    """Detect an agent log that ends before a terminal event."""

    trace = latest_agent_trace(trial_root, 0.0)
    return (
        trace.status == "metadata-checked"
        and trace.terminal_event_type is None
        and trace.last_status == "in-progress"
    )


def _failure_observation(
    stats: dict[str, Any],
    result_root: Path,
) -> tuple[str | None, str | None]:
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
        return None, None
    kind = kinds[0]
    if kind.startswith("AgentSetup"):
        phase = "agent-setup"
    elif kind == "AgentTimeoutError":
        phase = "agent-timeout"
    elif kind.startswith("Verifier"):
        phase = "verifier"
    elif kind == "NonZeroAgentExitCodeError":
        trial_names = [
            trial_name
            for mapping in exception_maps
            for names in mapping.values()
            if isinstance(names, list)
            for trial_name in names
            if isinstance(trial_name, str)
        ]
        for trial_name in trial_names:
            trial_result_path = result_root / trial_name / "result.json"
            try:
                trial_result = json.loads(
                    trial_result_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError, TypeError):
                continue
            exception_info = trial_result.get("exception_info")
            if not isinstance(exception_info, dict):
                continue
            message = " ".join(
                value.lower()
                for key in ("exception_message", "exception_traceback")
                if isinstance(value := exception_info.get(key), str)
            )
            if _has_provider_quota_marker(message):
                return "ProviderQuotaExceeded", "provider"
            agent_log_path = (
                result_root / trial_name / "agent" / "mini-swe-agent.txt"
            )
            try:
                agent_log = agent_log_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                agent_log = ""
            if _has_provider_quota_marker(agent_log):
                return "ProviderQuotaExceeded", "provider"
            if _trace_is_incomplete(result_root / trial_name):
                return "AgentExecutionIncomplete", "agent-execution"
        phase = "agent-execution"
        for trial_name in trial_names:
            trial_result_path = result_root / trial_name / "result.json"
            try:
                trial_result = json.loads(trial_result_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if trial_result.get("agent_execution") is None:
                phase = "agent-setup"
                break
    else:
        phase = "runner"
    return kind, phase


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
    failure_kind, failure_phase = (
        _failure_observation(stats, path.parent)
        if status == "errored"
        else (None, None)
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
