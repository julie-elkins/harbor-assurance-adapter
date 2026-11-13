from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from harbor_assurance_adapter.cohort_comparison import compare_cohorts
from harbor_assurance_adapter.evaluation import (
    ReceiptObservation,
    aggregate_receipts,
    load_manifest,
)
from harbor_assurance_adapter.job_evaluation import summarize_harbor_job


def _receipt(
    path: Path,
    *,
    status: str,
    benchmark_status: str,
    runner_status: str = "completed",
    errored_trials: int = 0,
    returncode: int | None = 0,
    timed_out: bool = False,
    output_capped: bool = False,
    atif_status: str = "passed",
    trace_status: str = "metadata-checked",
    cost: float | None = 1.25,
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "receipt-v1",
                "run_id": f"test-{path.stem}",
                "status": status,
                "benchmark": "terminal-bench",
                "benchmark_revision": "2.0",
                "agent": "codex",
                "agent_revision": "0.167.0",
                "model": "openai/gpt-5.5",
                "provider": "openai",
                "harness": "harbor",
                "harness_revision": "v0.9.0",
                "command_digest": "a" * 64,
                "task_count": 1,
                "attempts": 1,
                "estimated_cost_usd": 2.0,
                "max_total_cost_usd": 25.0,
                "elapsed_seconds": 10.0,
                "returncode": returncode,
                "timed_out": timed_out,
                "output_capped": output_capped,
                "trajectory_store": "local-only",
                "trajectory_digest": "b" * 64,
                "runner_result_status": runner_status,
                "runner_total_trials": 1,
                "runner_completed_trials": 1,
                "runner_errored_trials": errored_trials,
                "observed_cost_usd": cost,
                "atif_scan_status": atif_status,
                "assurance_status": "observed",
                "stop_condition": "stop-after-one-task-or-any-timeout-or-output-cap",
                "assurance_source": "atif",
                "benchmark_status": benchmark_status,
                "benchmark_score": 1.0 if benchmark_status == "passed" else 0.0,
                "benchmark_failure_kind": (
                    "VerifierEnvironmentFailure"
                    if benchmark_status == "invalid"
                    else None
                ),
                "benchmark_failure_phase": (
                    "verifier-setup" if benchmark_status == "invalid" else None
                ),
                "atif_step_count": 2,
                "atif_tool_call_count": 1,
                "failure_kind": None,
                "failure_phase": None,
                "agent_trace_status": trace_status,
                "agent_event_count": 3,
                "agent_last_event_type": "turn.completed",
                "agent_last_item_type": "agent-message",
                "agent_last_status": "completed",
                "agent_terminal_event_type": "turn.completed",
                "runner_successful_trials": 1 if errored_trials == 0 else 0,
            }
        ),
        encoding="utf-8",
    )


class EvaluationTests(unittest.TestCase):
    def test_manifest_loads_with_public_boundary(self) -> None:
        manifest = load_manifest(Path("docs/evaluation-manifest.toml"))
        self.assertEqual(manifest["study"]["visibility"], "public")
        self.assertEqual(len(manifest["agents"]), 3)

    def test_aggregate_keeps_execution_and_benchmark_denominators_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            passed = root / "passed.json"
            failed = root / "failed.json"
            refused = root / "refused.json"
            invalid = root / "invalid.json"
            _receipt(passed, status="completed", benchmark_status="passed")
            _receipt(failed, status="completed", benchmark_status="failed")
            _receipt(invalid, status="completed", benchmark_status="invalid")
            _receipt(
                refused,
                status="refused",
                benchmark_status="not-run",
                runner_status="errored",
                errored_trials=1,
                returncode=1,
                atif_status="unknown",
                trace_status="metadata-invalid",
                cost=0.5,
            )

            result = aggregate_receipts(
                (
                    ReceiptObservation("codex", "task-a", passed),
                    ReceiptObservation("codex", "task-b", failed),
                    ReceiptObservation("codex", "task-c", invalid),
                    ReceiptObservation("codex", "task-d", refused),
                )
            )[0]

        self.assertEqual(result.attempted_runs, 4)
        self.assertEqual(result.clean_executions, 3)
        self.assertEqual(result.benchmark_passes, 1)
        self.assertEqual(result.benchmark_observations, 2)
        self.assertEqual(result.benchmark_invalid_runs, 1)
        self.assertEqual(result.assurance_checked_runs, 3)
        self.assertEqual(result.execution_completion_rate, 3 / 4)
        self.assertEqual(result.benchmark_pass_rate, 1 / 4)
        self.assertEqual(result.conditional_benchmark_pass_rate, 1 / 3)
        self.assertEqual(result.benchmark_observation_rate, 2 / 3)
        self.assertEqual(result.assurance_evidence_rate, 3 / 4)
        self.assertEqual(result.observed_cost_usd, 4.25)

    def test_agent_jsonl_assurance_source_counts_as_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claude.json"
            _receipt(path, status="completed", benchmark_status="passed")
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update(
                {
                    "agent": "claude-code",
                    "assurance_source": "agent-jsonl",
                    "atif_scan_status": "not-applicable",
                    "assurance_status": "metadata-checked",
                }
            )
            path.write_text(json.dumps(data), encoding="utf-8")

            result = aggregate_receipts(
                (ReceiptObservation("claude-code", "task-a", path),)
            )[0]

        self.assertEqual(result.assurance_checked_runs, 1)
        self.assertEqual(result.assurance_evidence_rate, 1.0)

    def test_job_summary_preserves_task_denominator_without_raw_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "config.json").write_text(
                json.dumps(
                    {
                        "datasets": [
                            {
                                "name": "terminal-bench",
                                "version": "2.0",
                            }
                        ],
                        "agents": [
                            {
                                "name": "codex",
                                "model_name": "openai/gpt-5.5",
                                "kwargs": {"version": "0.167.0"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (job / "result.json").write_text(
                json.dumps({"stats": {"cost_usd": 1.5}}),
                encoding="utf-8",
            )
            for task, reward, cost in (
                ("task-pass", 1.0, 1.0),
                ("task-fail", 0.0, 0.5),
            ):
                task_dir = job / task
                task_dir.mkdir()
                (task_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "task_name": task,
                            "task_id": {
                                "git_commit_id": "public-task-revision"
                            },
                            "agent_result": {
                                "cost_usd": cost,
                                "provider_response": "do not export secret",
                            },
                            "verifier_result": {
                                "rewards": {"reward": reward}
                            },
                            "exception_info": None,
                            "prompt": "do not export prompt",
                        }
                    ),
                    encoding="utf-8",
                )

            summary = summarize_harbor_job(job)
            serialized = json.dumps(summary)

        self.assertEqual(summary["metrics"]["attempted_tasks"], 2)
        self.assertEqual(summary["metrics"]["clean_executions"], 2)
        self.assertEqual(summary["metrics"]["benchmark_passes"], 1)
        self.assertEqual(summary["metrics"]["benchmark_failures"], 1)
        self.assertNotIn("do not export", serialized)
        self.assertNotIn(str(job), serialized)

    def test_cohort_comparison_recomputes_public_results_and_task_deltas(self) -> None:
        comparison = compare_cohorts(Path("docs/cohort-comparison.toml"))

        self.assertEqual(comparison["schema_version"], "cohort-comparison-v1")
        self.assertEqual(comparison["comparison"]["task_count"], 10)
        cohorts = {cohort["id"]: cohort for cohort in comparison["cohorts"]}
        self.assertEqual(cohorts["codex"]["metrics"]["benchmark_passes"], 7)
        self.assertEqual(
            cohorts["mini-swe-agent-original"]["metrics"]["clean_executions"],
            9,
        )
        self.assertEqual(
            cohorts["mini-swe-agent-post-bridge"]["metrics"]["benchmark_passes"],
            9,
        )
        deltas = comparison["task_deltas_from_first_cohort"]
        qemu = next(
            delta
            for delta in deltas
            if delta["task"] == "qemu-startup" and delta["comparison"] == "codex"
        )
        self.assertEqual(qemu["benchmark_score_delta"], None)
        self.assertEqual(qemu["execution_status"]["baseline"], "errored")
        self.assertEqual(qemu["execution_status"]["comparison"], "completed")
        gpt2 = next(
            delta
            for delta in deltas
            if delta["task"] == "gpt2-codegolf"
            and delta["comparison"] == "mini-swe-agent-post-bridge"
        )
        self.assertEqual(gpt2["benchmark_score_delta"], 1.0)

    def test_cohort_comparison_refuses_tampered_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "result.json"
            config = root / "config.toml"
            manifest = root / "manifest.toml"
            shutil.copy("docs/results/codex-comparison-10-v3.json", result)
            shutil.copy("config/codex-comparison-10-2.0.toml", config)
            data = json.loads(result.read_text(encoding="utf-8"))
            data["metrics"]["benchmark_passes"] = 6
            result.write_text(json.dumps(data), encoding="utf-8")
            manifest.write_text(
                """
[comparison]
id = "tampered"
benchmark = "terminal-bench"
benchmark_revision = "2.0"
task_set = "comparison-suite-10"
task_set_revision = "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"
task_count = 10
attempts_per_task = 1

[[cohorts]]
id = "codex"
result = "result.json"
config = "config.toml"
""".strip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "benchmark_passes"):
                compare_cohorts(manifest)


if __name__ == "__main__":
    unittest.main()
