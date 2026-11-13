"""Apply three rules to public-safe multi-task Harbor summaries.

1. Keep task execution status separate from benchmark correctness.
2. Count benchmark observations only for clean executions.
3. Export metadata only; never export prompts, provider output, or trajectories.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .receipt import read_receipt


@dataclass(frozen=True)
class TaskEvaluation:
    """A task outcome with no trial identifiers or raw execution content."""

    task: str
    execution_status: str
    benchmark_status: str
    benchmark_score: float | None
    failure_class: str | None
    observed_cost_usd: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"invalid JSON metadata: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return value


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 6)
    return None


def _task_evaluation(path: Path) -> TaskEvaluation:
    data = _read_json(path)
    task = data.get("task_name")
    if not isinstance(task, str) or not task:
        raise ValueError(f"task result has no public task name: {path.name}")

    agent_result = data.get("agent_result")
    exception_info = data.get("exception_info")
    verifier_result = data.get("verifier_result")
    if isinstance(agent_result, dict) and exception_info is None and isinstance(
        verifier_result, dict
    ):
        execution_status = "completed"
    elif isinstance(exception_info, dict):
        execution_status = "errored"
    else:
        execution_status = "incomplete"

    reward = None
    if execution_status == "completed" and isinstance(verifier_result, dict):
        rewards = verifier_result.get("rewards")
        if isinstance(rewards, dict):
            reward = _number(rewards.get("reward"))

    if execution_status != "completed" or reward is None:
        benchmark_status = "not-observed"
    elif reward == 1.0:
        benchmark_status = "passed"
    elif reward == 0.0:
        benchmark_status = "failed"
    else:
        benchmark_status = "partial"

    if execution_status != "completed":
        failure_class = (
            "agent-setup"
            if not isinstance(agent_result, dict)
            else "agent-execution"
        )
    elif benchmark_status == "failed":
        failure_class = "task-correctness"
    elif benchmark_status == "not-observed":
        failure_class = "benchmark-observation"
    else:
        failure_class = None

    observed_cost = (
        _number(agent_result.get("cost_usd"))
        if isinstance(agent_result, dict)
        else None
    )
    return TaskEvaluation(
        task=task,
        execution_status=execution_status,
        benchmark_status=benchmark_status,
        benchmark_score=reward,
        failure_class=failure_class,
        observed_cost_usd=observed_cost,
    )


def _task_results(job_dir: Path) -> tuple[TaskEvaluation, ...]:
    results = [
        _task_evaluation(path / "result.json")
        for path in job_dir.iterdir()
        if path.is_dir() and (path / "result.json").is_file()
    ]
    if not results:
        raise ValueError("job contains no per-task result metadata.")
    return tuple(sorted(results, key=lambda result: result.task))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def summarize_harbor_job(
    job_dir: Path,
    *,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Build a public-safe report from a Harbor job and optional receipt."""

    job_dir = job_dir.resolve()
    aggregate = _read_json(job_dir / "result.json")
    config = _read_json(job_dir / "config.json")
    tasks = _task_results(job_dir)

    datasets = config.get("datasets")
    dataset = datasets[0] if isinstance(datasets, list) and datasets else {}
    if not isinstance(dataset, dict):
        dataset = {}
    agents = config.get("agents")
    agent_config = agents[0] if isinstance(agents, list) and agents else {}
    if not isinstance(agent_config, dict):
        agent_config = {}

    task_set_revision = None
    for task_dir in sorted(job_dir.iterdir()):
        result_path = task_dir / "result.json"
        if not task_dir.is_dir() or not result_path.is_file():
            continue
        task_data = _read_json(result_path)
        task_id = task_data.get("task_id")
        if isinstance(task_id, dict) and isinstance(task_id.get("git_commit_id"), str):
            task_set_revision = task_id["git_commit_id"]
            break

    stats = aggregate.get("stats")
    if not isinstance(stats, dict):
        stats = {}
    reported_cost = _number(stats.get("cost_usd"))
    attempted = len(tasks)
    clean_executions = sum(
        task.execution_status == "completed" for task in tasks
    )
    benchmark_observations = sum(
        task.execution_status == "completed"
        and task.benchmark_status in {"passed", "failed", "partial"}
        for task in tasks
    )
    benchmark_passes = sum(
        task.execution_status == "completed"
        and task.benchmark_status == "passed"
        for task in tasks
    )

    assurance: dict[str, object] = {
        "scope": "run-level",
        "status": "not-included",
        "atif_scan_status": "not-included",
    }
    if receipt_path is not None:
        receipt = read_receipt(receipt_path)
        assurance.update(
            status=receipt.assurance_status,
            atif_scan_status=receipt.atif_scan_status,
            assurance_source=receipt.assurance_source,
        )

    return {
        "schema_version": "job-evaluation-v1",
        "provenance": {
            "source": "terminal-bench",
            "benchmark": dataset.get("name"),
            "benchmark_revision": dataset.get("version"),
            "task_set_revision": task_set_revision,
            "agent": agent_config.get("name"),
            "model": agent_config.get("model_name"),
            "runner_revision": (
                agent_config.get("kwargs", {}).get("version")
                if isinstance(agent_config.get("kwargs"), dict)
                else None
            ),
        },
        "metrics": {
            "attempted_tasks": attempted,
            "clean_executions": clean_executions,
            "benchmark_observations": benchmark_observations,
            "benchmark_passes": benchmark_passes,
            "benchmark_failures": sum(
                task.execution_status == "completed"
                and task.benchmark_status == "failed"
                for task in tasks
            ),
            "execution_completion_rate": _rate(clean_executions, attempted),
            "benchmark_pass_rate": _rate(benchmark_passes, attempted),
            "conditional_benchmark_pass_rate": _rate(
                benchmark_passes, clean_executions
            ),
            "benchmark_observation_rate": _rate(
                benchmark_observations, clean_executions
            ),
            "observed_cost_usd": reported_cost,
        },
        "assurance": assurance,
        "tasks": [task.to_dict() for task in tasks],
    }


def job_summary_to_json(
    job_dir: Path,
    *,
    receipt_path: Path | None = None,
) -> str:
    """Serialize a public-safe Harbor job summary."""

    return json.dumps(
        summarize_harbor_job(job_dir, receipt_path=receipt_path),
        indent=2,
        sort_keys=True,
    )
