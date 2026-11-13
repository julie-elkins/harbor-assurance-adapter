"""Apply four rules to offline cohort comparison.

1. Read only public metadata and never load raw trajectories or provider output.
2. Validate each result against the comparison manifest and its source config.
3. Recompute metrics from task records instead of trusting aggregate fields.
4. Refuse a comparison when the cohorts are not metadata-compatible.
"""

from __future__ import annotations

import json
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import load_config


# FIELD CONVENTION: these are the checked-in public report schema names.
_SCHEMA_VERSION = "job-evaluation-v1"
_COMPARISON_SCHEMA_VERSION = "cohort-comparison-v1"
# FIELD CONVENTION: these statuses are the benchmark observations defined in
# docs/metrics.md; a missing observation is not a benchmark failure.
_OBSERVED_BENCHMARK_STATUSES = frozenset({"passed", "failed", "partial"})


@dataclass(frozen=True)
class CohortSpec:
    """One public result and the config that claims to have produced it."""

    cohort_id: str
    result_path: Path
    config_path: Path


@dataclass(frozen=True)
class ComparisonSpec:
    """Pinned metadata shared by all cohorts in a comparison."""

    comparison_id: str
    benchmark: str
    benchmark_revision: str
    task_set: str
    task_set_revision: str
    task_count: int
    attempts_per_task: int
    cohorts: tuple[CohortSpec, ...]


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid JSON metadata: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _resolve_manifest_path(base_dir: Path, value: object, field: str) -> Path:
    relative = Path(_required_string(value, field))
    if relative.is_absolute():
        raise ValueError(f"{field} must be relative to the comparison manifest.")
    path = (base_dir / relative).resolve()
    if not path.is_file():
        raise ValueError(f"{field} does not exist: {relative}")
    return path


def load_comparison_manifest(path: Path) -> ComparisonSpec:
    """Load a comparison manifest without executing a provider command."""

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid comparison manifest: {path}") from exc

    comparison = data.get("comparison")
    cohorts = data.get("cohorts")
    if not isinstance(comparison, dict) or not isinstance(cohorts, list):
        raise ValueError("manifest must contain [comparison] and [[cohorts]].")
    if not cohorts:
        raise ValueError("manifest must contain at least one cohort.")

    specs: list[CohortSpec] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(cohorts):
        if not isinstance(value, dict):
            raise ValueError(f"cohorts[{index}] must be a table.")
        cohort_id = _required_string(value.get("id"), f"cohorts[{index}].id")
        if cohort_id in seen_ids:
            raise ValueError(f"duplicate cohort id: {cohort_id}")
        seen_ids.add(cohort_id)
        specs.append(
            CohortSpec(
                cohort_id=cohort_id,
                result_path=_resolve_manifest_path(
                    path.parent, value.get("result"), f"cohorts[{index}].result"
                ),
                config_path=_resolve_manifest_path(
                    path.parent, value.get("config"), f"cohorts[{index}].config"
                ),
            )
        )

    return ComparisonSpec(
        comparison_id=_required_string(comparison.get("id"), "comparison.id"),
        benchmark=_required_string(comparison.get("benchmark"), "comparison.benchmark"),
        benchmark_revision=_required_string(
            comparison.get("benchmark_revision"), "comparison.benchmark_revision"
        ),
        task_set=_required_string(comparison.get("task_set"), "comparison.task_set"),
        task_set_revision=_required_string(
            comparison.get("task_set_revision"), "comparison.task_set_revision"
        ),
        task_count=_positive_int(comparison.get("task_count"), "comparison.task_count"),
        attempts_per_task=_positive_int(
            comparison.get("attempts_per_task"), "comparison.attempts_per_task"
        ),
        cohorts=tuple(specs),
    )


def _normalise_revision(value: object) -> str:
    return value[1:] if isinstance(value, str) and value.startswith("v") else str(value)


def _number(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric or null.")
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{field} must be a finite non-negative number or null.")
    return round(float(value), 6)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _task_map(data: dict[str, Any], cohort_id: str) -> dict[str, dict[str, Any]]:
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError(f"{cohort_id} result must contain a non-empty tasks list.")
    result: dict[str, dict[str, Any]] = {}
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"{cohort_id} task {index} must be an object.")
        name = _required_string(task.get("task"), f"{cohort_id} task {index}.task")
        if name in result:
            raise ValueError(f"{cohort_id} contains duplicate task: {name}")
        execution_status = _required_string(
            task.get("execution_status"),
            f"{cohort_id} task {name}.execution_status",
        )
        benchmark_status = _required_string(
            task.get("benchmark_status"),
            f"{cohort_id} task {name}.benchmark_status",
        )
        if execution_status not in {"completed", "errored", "incomplete"}:
            raise ValueError(f"{cohort_id} task {name} has unknown execution status.")
        if benchmark_status not in {
            "passed",
            "failed",
            "partial",
            "not-observed",
        }:
            raise ValueError(f"{cohort_id} task {name} has unknown benchmark status.")
        if execution_status != "completed" and benchmark_status != "not-observed":
            raise ValueError(
                f"{cohort_id} task {name} reports benchmark status for "
                "a non-completed execution."
            )
        score = _number(task.get("benchmark_score"), f"{cohort_id} task {name}.score")
        cost = _number(
            task.get("observed_cost_usd"),
            f"{cohort_id} task {name}.observed_cost_usd",
        )
        result[name] = {
            "task": name,
            "execution_status": execution_status,
            "benchmark_status": benchmark_status,
            "benchmark_score": score,
            "observed_cost_usd": cost,
        }
    return result


def _computed_metrics(tasks: dict[str, dict[str, Any]]) -> dict[str, object]:
    attempted = len(tasks)
    clean = sum(task["execution_status"] == "completed" for task in tasks.values())
    observed = sum(
        task["execution_status"] == "completed"
        and task["benchmark_status"] in _OBSERVED_BENCHMARK_STATUSES
        for task in tasks.values()
    )
    passes = sum(
        task["execution_status"] == "completed"
        and task["benchmark_status"] == "passed"
        for task in tasks.values()
    )
    failures = sum(
        task["execution_status"] == "completed"
        and task["benchmark_status"] == "failed"
        for task in tasks.values()
    )
    costs = [
        task["observed_cost_usd"]
        for task in tasks.values()
        if task["observed_cost_usd"] is not None
    ]
    return {
        "attempted_tasks": attempted,
        "clean_executions": clean,
        "benchmark_observations": observed,
        "benchmark_passes": passes,
        "benchmark_failures": failures,
        "execution_completion_rate": _rate(clean, attempted),
        "benchmark_pass_rate": _rate(passes, attempted),
        "conditional_benchmark_pass_rate": _rate(passes, clean),
        "benchmark_observation_rate": _rate(observed, clean),
        "observed_cost_usd": round(sum(costs), 6) if costs else None,
        "cost_observations": len(costs),
    }


def _same_number(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-6)


def _validate_report(
    spec: ComparisonSpec,
    cohort: CohortSpec,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, object]]:
    data = _read_json(cohort.result_path)
    if data.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError(
            f"{cohort.cohort_id} must use {_SCHEMA_VERSION}; "
            f"found {data.get('schema_version')!r}."
        )
    provenance = data.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(f"{cohort.cohort_id} result has no provenance object.")
    for field, expected in (
        ("benchmark", spec.benchmark),
        ("benchmark_revision", spec.benchmark_revision),
    ):
        if provenance.get(field) != expected:
            raise ValueError(
                f"{cohort.cohort_id} {field} does not match the comparison manifest."
            )
    if provenance.get("task_set_revision") != spec.task_set_revision:
        raise ValueError(
            f"{cohort.cohort_id} task_set_revision does not match the manifest."
        )

    config = load_config(cohort.config_path)
    for field, expected in (
        ("benchmark", provenance.get("benchmark")),
        ("benchmark_revision", provenance.get("benchmark_revision")),
        ("agent", provenance.get("agent")),
        ("model", provenance.get("model")),
    ):
        if getattr(config, field) != expected:
            raise ValueError(
                f"{cohort.cohort_id} config {field} does not match its result."
            )
    if config.budget.task_count != spec.task_count:
        raise ValueError(f"{cohort.cohort_id} config task count does not match the manifest.")
    if config.budget.attempts != spec.attempts_per_task:
        raise ValueError(
            f"{cohort.cohort_id} config attempt count does not match the manifest."
        )
    result_agent_revision = provenance.get("runner_revision")
    if result_agent_revision is not None and _normalise_revision(
        config.agent_revision
    ) != _normalise_revision(result_agent_revision):
        raise ValueError(
            f"{cohort.cohort_id} config agent_revision does not match its result."
        )

    tasks = _task_map(data, cohort.cohort_id)
    if len(tasks) != spec.task_count:
        raise ValueError(
            f"{cohort.cohort_id} has {len(tasks)} tasks; "
            f"expected {spec.task_count}."
        )
    computed = _computed_metrics(tasks)
    reported = data.get("metrics")
    if not isinstance(reported, dict):
        raise ValueError(f"{cohort.cohort_id} result has no metrics object.")
    for field, expected in computed.items():
        if field not in reported:
            if field == "cost_observations":
                continue
            raise ValueError(f"{cohort.cohort_id} metrics omit {field}.")
        if isinstance(expected, float):
            if not _same_number(reported[field], expected):
                raise ValueError(
                    f"{cohort.cohort_id} metric {field} does not match its tasks."
                )
        elif reported[field] != expected:
            raise ValueError(
                f"{cohort.cohort_id} metric {field} does not match its tasks."
            )
    return data, tasks, computed


def _task_deltas(
    baseline_id: str,
    baseline: dict[str, dict[str, Any]],
    comparison_id: str,
    comparison: dict[str, dict[str, Any]],
) -> list[dict[str, object]]:
    deltas: list[dict[str, object]] = []
    for task_name in sorted(baseline):
        before = baseline[task_name]
        after = comparison[task_name]
        before_score = before["benchmark_score"]
        after_score = after["benchmark_score"]
        score_delta = (
            round(after_score - before_score, 6)
            if before_score is not None and after_score is not None
            else None
        )
        before_cost = before["observed_cost_usd"]
        after_cost = after["observed_cost_usd"]
        cost_delta = (
            round(after_cost - before_cost, 6)
            if before_cost is not None and after_cost is not None
            else None
        )
        deltas.append(
            {
                "task": task_name,
                "baseline": baseline_id,
                "comparison": comparison_id,
                "execution_status": {
                    "baseline": before["execution_status"],
                    "comparison": after["execution_status"],
                },
                "benchmark_status": {
                    "baseline": before["benchmark_status"],
                    "comparison": after["benchmark_status"],
                },
                "benchmark_score_delta": score_delta,
                "observed_cost_delta_usd": cost_delta,
            }
        )
    return deltas


def compare_cohorts(path: Path) -> dict[str, object]:
    """Validate and compare public cohort reports without provider calls."""

    spec = load_comparison_manifest(path)
    validated: list[
        tuple[CohortSpec, dict[str, Any], dict[str, dict[str, Any]], dict[str, object]]
    ] = []
    for cohort in spec.cohorts:
        validated.append((cohort, *_validate_report(spec, cohort)))

    task_names = set(validated[0][2])
    for cohort, _, tasks, _ in validated[1:]:
        if set(tasks) != task_names:
            raise ValueError(
                f"{cohort.cohort_id} task set does not match the first cohort."
            )

    cohorts: list[dict[str, object]] = []
    for cohort, data, _, metrics in validated:
        provenance = data["provenance"]
        assurance = data.get("assurance")
        assurance_checked = (
            isinstance(assurance, dict)
            and assurance.get("status") == "metadata-checked"
        )
        cohorts.append(
            {
                "id": cohort.cohort_id,
                "agent": provenance.get("agent"),
                "model": provenance.get("model"),
                "runner_revision": provenance.get("runner_revision"),
                "config": cohort.config_path.name,
                "assurance_checked": assurance_checked,
                "metrics": metrics,
            }
        )

    baseline_id = validated[0][0].cohort_id
    baseline_tasks = validated[0][2]
    deltas = []
    for cohort, _, tasks, _ in validated[1:]:
        deltas.extend(_task_deltas(baseline_id, baseline_tasks, cohort.cohort_id, tasks))

    return {
        "schema_version": _COMPARISON_SCHEMA_VERSION,
        "comparison": {
            "id": spec.comparison_id,
            "benchmark": spec.benchmark,
            "benchmark_revision": spec.benchmark_revision,
            "task_set": spec.task_set,
            "task_set_revision": spec.task_set_revision,
            "task_count": spec.task_count,
            "attempts_per_task": spec.attempts_per_task,
            "cohort_count": len(spec.cohorts),
        },
        "cohorts": cohorts,
        "task_deltas_from_first_cohort": deltas,
        "validation": {
            "status": "passed",
            "source": "public-job-evaluation-metadata",
            "raw_trajectories": "excluded",
            "provider_responses": "excluded",
            "secrets": "excluded",
        },
    }
