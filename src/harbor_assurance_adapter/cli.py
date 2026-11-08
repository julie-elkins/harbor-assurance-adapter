"""Command-line entry points for the bounded adapter."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from dataclasses import replace
from pathlib import Path

from .aah import main as aah_main
from .agent_trace import AgentTraceSummary, latest_agent_trace
from .atif import AtifScanResult, latest_trajectory, scan_trajectory
from .job_evaluation import summarize_harbor_job
from .models import load_config
from .process import ProcessResult, missing_environment, run_bounded
from .receipt import make_receipt, write_receipt
from .runner_result import RunnerResult, latest_result


def _config_path(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError("configuration file does not exist.")
    return path


def _assurance_projection(
    agent: str,
    atif_scan: AtifScanResult,
    agent_trace: AgentTraceSummary,
) -> tuple[str, str, str]:
    """Choose an explicit local evidence source without hiding ATIF failures."""

    if (
        agent == "claude-code"
        and atif_scan.status == "missing"
        and agent_trace.status == "metadata-checked"
        and agent_trace.terminal_event_type is not None
    ):
        # Claude Code's Harbor profile currently emits a complete JSONL event
        # log but no ATIF file. Keep `atif_scan_status` truthful and use the
        # separate event-log evidence source rather than pretending the log is
        # ATIF. A malformed ATIF file must remain a refusal, so this fallback
        # applies only to a missing artifact.
        return "not-applicable", "metadata-checked", "agent-jsonl"
    return atif_scan.status, atif_scan.assurance_status, "atif"


def _process_boundary_projection(
    result: ProcessResult,
    runner_result: RunnerResult,
) -> RunnerResult:
    """Record failures caused by the adapter's own bounded process boundary."""

    if result.timed_out:
        return replace(
            runner_result,
            failure_kind="AdapterTimeout",
            failure_phase="adapter",
        )
    if result.output_capped:
        return replace(
            runner_result,
            failure_kind="AdapterOutputCap",
            failure_phase="adapter",
        )
    return runner_result


def _run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.dry_run:
        receipt = make_receipt(config, None, status="planned")
        write_receipt(args.receipt, receipt)
        print(json.dumps({"status": "planned", "receipt": str(args.receipt)}))
        return 0
    executable = shutil.which(config.command[0])
    if executable is None and not Path(config.command[0]).is_file():
        raise SystemExit(f"configured command is not installed: {config.command[0]}")
    missing_env = missing_environment(config.pass_env)
    if missing_env:
        receipt = make_receipt(
            config,
            None,
            status="refused",
            runner_result=RunnerResult(
                status="not-run",
                failure_kind="MissingCredential",
                failure_phase="preflight",
            ),
        )
        write_receipt(args.receipt, receipt)
        print(
            json.dumps(
                {
                    "status": "refused",
                    "receipt": str(args.receipt),
                    "reason": "missing-credential",
                    "missing_environment": list(missing_env),
                }
            )
        )
        return 1
    raw_dir = config.raw_run_dir / "latest"
    started_epoch = time.time()
    result = run_bounded(
        config.command,
        workdir=config.workdir,
        raw_dir=raw_dir,
        timeout_seconds=config.budget.timeout_seconds,
        max_output_bytes=config.budget.max_output_bytes,
        pass_env=config.pass_env,
        path_prefix=(
            (config.workdir / config.path_prefix).resolve()
            if config.path_prefix is not None
            else None
        ),
    )
    runner_result = latest_result(
        (config.workdir / config.jobs_dir).resolve(),
        started_epoch,
    )
    runner_result = _process_boundary_projection(result, runner_result)
    trajectory = latest_trajectory(
        (config.workdir / config.jobs_dir).resolve(),
        started_epoch,
    )
    atif_scan = scan_trajectory(trajectory)
    agent_trace = latest_agent_trace(
        (config.workdir / config.jobs_dir).resolve(),
        started_epoch,
    )
    atif_scan_status, assurance_status, assurance_source = _assurance_projection(
        config.agent,
        atif_scan,
        agent_trace,
    )
    status = (
        "completed"
        if (
            result.returncode == 0
            and not result.timed_out
            and not result.output_capped
            and runner_result.clean
        )
        else "refused"
    )
    receipt = make_receipt(
        config,
        result,
        status=status,
        runner_result=runner_result,
        atif_scan_status=atif_scan_status,
        assurance_status=assurance_status,
        trajectory_digest=atif_scan.trajectory_digest,
        atif_step_count=atif_scan.step_count,
        atif_tool_call_count=atif_scan.tool_call_count,
        agent_trace=agent_trace,
        assurance_source=assurance_source,
    )
    write_receipt(args.receipt, receipt)
    print(
        json.dumps(
            {
                "status": status,
                "receipt": str(args.receipt),
                "returncode": result.returncode,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
            }
        )
    )
    return 0 if status == "completed" else 1


def _summarize_job(args: argparse.Namespace) -> int:
    summary = summarize_harbor_job(args.job, receipt_path=args.receipt)
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(serialized, end="")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    print(json.dumps({"status": "written", "output": str(args.output)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a bounded Harbor command and project metadata into AAH."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the configured command")
    run_parser.add_argument("--config", type=_config_path, required=True)
    run_parser.add_argument("--receipt", type=Path, required=True)
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate configuration and write a planned receipt without execution",
    )
    run_parser.set_defaults(handler=_run)

    summary_parser = subparsers.add_parser(
        "summarize-job",
        help="emit a public-safe per-task summary of a Harbor job",
    )
    summary_parser.add_argument("--job", type=Path, required=True)
    summary_parser.add_argument("--receipt", type=Path)
    summary_parser.add_argument("--output", type=Path)
    summary_parser.set_defaults(handler=_summarize_job)

    aah_parser = subparsers.add_parser(
        "aah-adapter",
        help="read AAH JSONL requests and emit metadata-only responses",
    )
    aah_parser.add_argument("--receipt", type=Path)
    aah_parser.set_defaults(handler=lambda args: aah_main(["--receipt", str(args.receipt)] if args.receipt else []))

    args = parser.parse_args(argv)
    return args.handler(args)
