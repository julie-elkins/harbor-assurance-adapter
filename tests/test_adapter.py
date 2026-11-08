from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harbor_assurance_adapter.aah import _response
from harbor_assurance_adapter.agent_trace import AgentTraceSummary
from harbor_assurance_adapter.atif import AtifScanResult
from harbor_assurance_adapter.cli import (
    _assurance_projection,
    _process_boundary_projection,
)
from harbor_assurance_adapter.models import (
    Budget,
    RunConfig,
    load_config,
    receipt_from_dict,
    receipt_to_dict,
)
from harbor_assurance_adapter.receipt import make_receipt
from harbor_assurance_adapter.runner_result import RunnerResult


def config(tmp: Path) -> RunConfig:
    return RunConfig(
        benchmark="terminal-bench",
        benchmark_revision="pinned-release",
        agent="mini-swe-agent",
        agent_revision="v2.4.6",
        model="model-id",
        provider="provider-id",
        harness="harbor",
        harness_revision="pinned-release",
        pass_env=(),
        path_prefix=None,
        workdir=tmp,
        raw_run_dir=tmp / "runs",
        jobs_dir=tmp / "jobs",
        command=("harbor", "run", "--dataset", "terminal-bench@pinned-release"),
        budget=Budget(
            max_total_cost_usd=25.0,
            estimated_cost_per_task_usd=0.53,
            task_count=1,
            attempts=1,
            timeout_seconds=60.0,
            max_output_bytes=1024,
            stop_condition="stop-after-one-task",
        ),
    )


class AdapterTests(unittest.TestCase):
    def test_claude_missing_atif_uses_explicit_jsonl_assurance_source(self) -> None:
        atif = AtifScanResult(
            status="missing",
            assurance_status="metadata-unavailable",
        )
        trace = AgentTraceSummary(
            status="metadata-checked",
            event_count=10,
            tool_call_count=2,
            log_digest="a" * 64,
            terminal_event_type="result",
        )

        result = _assurance_projection("claude-code", atif, trace)

        self.assertEqual(
            result,
            ("not-applicable", "metadata-checked", "agent-jsonl"),
        )

    def test_malformed_atif_is_not_hidden_by_claude_jsonl_fallback(self) -> None:
        atif = AtifScanResult(
            status="invalid",
            assurance_status="metadata-refused",
        )
        trace = AgentTraceSummary(status="metadata-checked", event_count=10)

        result = _assurance_projection("claude-code", atif, trace)

        self.assertEqual(result, ("invalid", "metadata-refused", "atif"))

    def test_claude_trace_without_terminal_event_is_not_assurance_evidence(self) -> None:
        atif = AtifScanResult(
            status="missing",
            assurance_status="metadata-unavailable",
        )
        trace = AgentTraceSummary(
            status="metadata-checked",
            event_count=10,
            tool_call_count=2,
            log_digest="a" * 64,
            last_status="in-progress",
        )

        result = _assurance_projection("claude-code", atif, trace)

        self.assertEqual(result, ("missing", "metadata-unavailable", "atif"))

    def test_timed_out_process_is_classified_at_adapter_boundary(self) -> None:
        from harbor_assurance_adapter.models import ProcessResult

        runner = RunnerResult(status="errored", total_trials=1)
        result = _process_boundary_projection(
            ProcessResult(
                returncode=-9,
                elapsed_seconds=3600.0,
                timed_out=True,
                output_capped=False,
                stdout_bytes=0,
                stderr_bytes=0,
            ),
            runner,
        )

        self.assertEqual(result.failure_kind, "AdapterTimeout")
        self.assertEqual(result.failure_phase, "adapter")

    def test_prepared_configs_align_agent_timeout_with_adapter_budget(self) -> None:
        repository = Path(__file__).parents[1]
        for name in (
            "mini-swe-agent-smoke.toml",
            "mini-swe-agent-live-2.0.toml",
            "claude-code-live-2.0.toml",
            "codex-live-2.0.toml",
            "codex-isolation-fix-git-2.0.toml",
            "codex-batch-gpt2-codegolf-2.0.toml",
            "codex-batch-regex-log-2.0.toml",
            "codex-batch-sanitize-git-repo-2.0.toml",
            "codex-comparison-10-2.0.toml",
            "claude-code-comparison-10-2.0.toml",
            "mini-swe-agent-comparison-10-2.0.toml",
        ):
            run_config = load_config(repository / "config" / name)
            command = list(run_config.command)
            self.assertIn("--agent-timeout-multiplier", command)
            index = command.index("--agent-timeout-multiplier")
            self.assertEqual(command[index + 1], "4")

    def test_claude_code_config_is_pinned_and_budgeted(self) -> None:
        repository = Path(__file__).parents[1]
        run_config = load_config(repository / "config" / "claude-code-live-2.0.toml")

        self.assertEqual(run_config.agent, "claude-code")
        self.assertEqual(run_config.agent_revision, "2.1.319")
        self.assertEqual(run_config.budget.max_total_cost_usd, 25.0)
        self.assertEqual(run_config.budget.estimated_cost_per_task_usd, 15.0)
        self.assertIn("version=2.1.319", run_config.command)
        self.assertIn("max_budget_usd=15", run_config.command)

    def test_codex_config_is_pinned_and_budgeted(self) -> None:
        repository = Path(__file__).parents[1]
        run_config = load_config(repository / "config" / "codex-live-2.0.toml")

        self.assertEqual(run_config.agent, "codex")
        self.assertEqual(run_config.agent_revision, "0.167.0")
        self.assertEqual(run_config.model, "openai/gpt-5.5")
        self.assertEqual(run_config.provider, "openai")
        self.assertEqual(run_config.budget.max_total_cost_usd, 25.0)
        self.assertEqual(run_config.budget.estimated_cost_per_task_usd, 15.0)
        self.assertIn("version=0.167.0", run_config.command)
        self.assertIn("reasoning_effort=high", run_config.command)

    def test_codex_isolation_config_selects_one_easy_task(self) -> None:
        repository = Path(__file__).parents[1]
        run_config = load_config(
            repository / "config" / "codex-isolation-fix-git-2.0.toml"
        )

        self.assertEqual(run_config.agent, "codex")
        self.assertEqual(run_config.model, "openai/gpt-5.5")
        self.assertEqual(run_config.budget.estimated_cost_per_task_usd, 5.0)
        self.assertIn("--include-task-name", run_config.command)
        index = run_config.command.index("--include-task-name")
        self.assertEqual(run_config.command[index + 1], "fix-git")

    def test_budget_rejects_estimate_above_ceiling(self) -> None:
        budget = Budget(
            max_total_cost_usd=1.0,
            estimated_cost_per_task_usd=0.53,
            task_count=2,
            attempts=1,
            timeout_seconds=60.0,
            max_output_bytes=1024,
            stop_condition="stop",
        )
        with self.assertRaises(ValueError):
            budget.validate()

    def test_receipt_is_round_trippable_and_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_config = config(Path(directory))
            receipt = make_receipt(run_config, None, status="planned")
            data = receipt_to_dict(receipt)
            serialized = json.dumps(data)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("tool_arguments", serialized)
            self.assertEqual(receipt_from_dict(data), receipt)

    def test_aah_projection_contains_no_raw_request_content(self) -> None:
        response = _response(
            {"scenario_id": "synthetic-scenario-1", "task_label": "safe"},
            None,
        )
        serialized = json.dumps(response)
        self.assertIn("metadata-only", serialized)
        self.assertNotIn("secret", serialized)
        self.assertEqual(response["events"][0]["sequence"], 1)
        self.assertEqual(response["trace"]["atif_scan_status"], "synthetic")
        self.assertEqual(response["trace"]["assurance_source"], "synthetic")

    def test_completed_receipt_requires_clean_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_config = config(Path(directory))
            from harbor_assurance_adapter.models import ProcessResult

            with self.assertRaises(ValueError):
                make_receipt(
                    run_config,
                    ProcessResult(
                        returncode=1,
                        elapsed_seconds=1.0,
                        timed_out=False,
                        output_capped=False,
                        stdout_bytes=0,
                        stderr_bytes=0,
                    ),
                    status="completed",
                )

    def test_completed_receipt_requires_clean_harbor_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_config = config(Path(directory))
            from harbor_assurance_adapter.models import ProcessResult

            with self.assertRaises(ValueError):
                make_receipt(
                    run_config,
                    ProcessResult(
                        returncode=0,
                        elapsed_seconds=1.0,
                        timed_out=False,
                        output_capped=False,
                        stdout_bytes=0,
                        stderr_bytes=0,
                    ),
                    status="completed",
                    runner_result=RunnerResult(
                        status="errored",
                        total_trials=1,
                        completed_trials=1,
                        errored_trials=1,
                    ),
                )

    def test_completed_execution_records_failed_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_config = config(Path(directory))
            from harbor_assurance_adapter.models import ProcessResult

            receipt = make_receipt(
                run_config,
                ProcessResult(
                    returncode=0,
                    elapsed_seconds=1.0,
                    timed_out=False,
                    output_capped=False,
                    stdout_bytes=0,
                    stderr_bytes=0,
                ),
                status="completed",
                runner_result=RunnerResult(
                    status="completed",
                    total_trials=1,
                    completed_trials=1,
                    errored_trials=0,
                    benchmark_status="failed",
                    benchmark_score=0.0,
                ),
                atif_scan_status="passed",
                assurance_status="metadata-checked",
                trajectory_digest="a" * 64,
                atif_step_count=2,
                atif_tool_call_count=1,
            )

        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.benchmark_status, "failed")
        self.assertEqual(receipt.benchmark_score, 0.0)
        self.assertEqual(receipt.atif_scan_status, "passed")
        self.assertEqual(receipt.atif_step_count, 2)
        self.assertEqual(receipt.atif_tool_call_count, 1)
        self.assertEqual(receipt.runner_successful_trials, 1)

    def test_refused_receipt_records_runner_failure_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_config = config(Path(directory))
            from harbor_assurance_adapter.models import ProcessResult

            receipt = make_receipt(
                run_config,
                ProcessResult(
                    returncode=1,
                    elapsed_seconds=2.0,
                    timed_out=False,
                    output_capped=False,
                    stdout_bytes=12,
                    stderr_bytes=0,
                ),
                status="refused",
                runner_result=RunnerResult(
                    status="errored",
                    total_trials=1,
                    completed_trials=1,
                    errored_trials=1,
                    failure_kind="NonZeroAgentExitCodeError",
                    failure_phase="agent-execution",
                ),
                agent_trace=AgentTraceSummary(
                    status="metadata-checked",
                    event_count=3,
                    last_event_type="item.started",
                    last_item_type="command-execution",
                    last_status="in-progress",
                ),
            )

        self.assertEqual(receipt.failure_kind, "NonZeroAgentExitCodeError")
        self.assertEqual(receipt.failure_phase, "agent-execution")
        self.assertEqual(receipt.agent_trace_status, "metadata-checked")
        self.assertEqual(receipt.agent_event_count, 3)
        self.assertEqual(receipt.assurance_source, "atif")
        self.assertEqual(receipt.agent_last_event_type, "item.started")
        self.assertIsNone(receipt.agent_terminal_event_type)


if __name__ == "__main__":
    unittest.main()
