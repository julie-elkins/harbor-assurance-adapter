"""Receipt creation and local persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import RunConfig, RunReceipt, command_digest, run_id
from .process import ProcessResult
from .runner_result import RunnerResult
from .agent_trace import AgentTraceSummary


def _digest_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_receipt(
    config: RunConfig,
    result: ProcessResult | None,
    *,
    status: str,
    atif_scan_status: str = "not-run",
    assurance_status: str = "not-run",
    trajectory_digest: str | None = None,
    atif_step_count: int | None = None,
    atif_tool_call_count: int | None = None,
    atif_schema_version: str | None = None,
    runner_result: RunnerResult | None = None,
    agent_trace: AgentTraceSummary | None = None,
    assurance_source: str = "atif",
) -> RunReceipt:
    """Reduce one execution to identifiers and bounded observations."""

    config.validate()
    if result is None:
        elapsed = 0.0
        returncode = None
        timed_out = False
        output_capped = False
    else:
        elapsed = result.elapsed_seconds
        returncode = result.returncode
        timed_out = result.timed_out
        output_capped = result.output_capped
    if status == "completed" and (
        returncode != 0 or timed_out or output_capped or runner_result is None or not runner_result.clean
    ):
        raise ValueError(
            "completed receipt requires a clean bounded process result and "
            "a Harbor result with zero errored trials."
        )
    if runner_result is None:
        runner_result = RunnerResult(status="not-run")
    if agent_trace is None:
        agent_trace = AgentTraceSummary(status="not-run")
    receipt = RunReceipt(
        schema_version="receipt-v1",
        run_id=run_id(config),
        status=status,
        benchmark=config.benchmark,
        benchmark_revision=config.benchmark_revision,
        agent=config.agent,
        agent_revision=config.agent_revision,
        model=config.model,
        provider=config.provider,
        harness=config.harness,
        harness_revision=config.harness_revision,
        command_digest=command_digest(config.command),
        task_count=config.budget.task_count,
        attempts=config.budget.attempts,
        estimated_cost_usd=(
            config.budget.estimated_total_cost_usd()
            if result is not None
            else 0.0
        ),
        max_total_cost_usd=config.budget.max_total_cost_usd,
        elapsed_seconds=elapsed,
        returncode=returncode,
        timed_out=timed_out,
        output_capped=output_capped,
        trajectory_store="local-only",
        trajectory_digest=trajectory_digest,
        runner_result_status=runner_result.status,
        runner_total_trials=runner_result.total_trials,
        runner_completed_trials=runner_result.completed_trials,
        runner_errored_trials=runner_result.errored_trials,
        observed_cost_usd=runner_result.observed_cost_usd,
        atif_scan_status=atif_scan_status,
        assurance_status=assurance_status,
        stop_condition=config.budget.stop_condition,
        assurance_source=assurance_source,
        benchmark_status=runner_result.benchmark_status,
        benchmark_score=runner_result.benchmark_score,
        benchmark_failure_kind=runner_result.benchmark_failure_kind,
        benchmark_failure_phase=runner_result.benchmark_failure_phase,
        atif_step_count=atif_step_count,
        atif_tool_call_count=atif_tool_call_count,
        atif_schema_version=atif_schema_version,
        failure_kind=runner_result.failure_kind,
        failure_phase=runner_result.failure_phase,
        failure_breakdown=runner_result.failure_breakdown,
        agent_trace_status=agent_trace.status,
        agent_event_count=agent_trace.event_count,
        agent_tool_call_count=agent_trace.tool_call_count,
        agent_log_digest=agent_trace.log_digest,
        agent_last_event_type=agent_trace.last_event_type,
        agent_last_item_type=agent_trace.last_item_type,
        agent_last_status=agent_trace.last_status,
        agent_terminal_event_type=agent_trace.terminal_event_type,
        runner_successful_trials=runner_result.successful_trials,
    )
    receipt.validate()
    return receipt


def write_receipt(path: Path, receipt: RunReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt_to_json(receipt), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_receipt(path: Path) -> RunReceipt:
    from .models import receipt_from_dict

    return receipt_from_dict(json.loads(path.read_text(encoding="utf-8")))


def receipt_to_json(receipt: RunReceipt) -> dict[str, object]:
    from .models import receipt_to_dict

    return receipt_to_dict(receipt)
