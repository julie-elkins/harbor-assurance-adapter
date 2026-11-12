from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harbor_assurance_adapter.cli import main
from harbor_assurance_adapter.evidence_summary import receipt_to_evidence_summary
from harbor_assurance_adapter.models import Budget, ProcessResult, RunConfig
from harbor_assurance_adapter.receipt import make_receipt, write_receipt
from harbor_assurance_adapter.runner_result import RunnerResult


def _config(tmp: Path) -> RunConfig:
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
        command=("harbor", "run"),
        budget=Budget(
            max_total_cost_usd=25.0,
            estimated_cost_per_task_usd=1.0,
            task_count=1,
            attempts=1,
            timeout_seconds=60.0,
            max_output_bytes=1024,
            stop_condition="stop-after-one-task",
        ),
    )


def _receipt(tmp: Path, *, atif_status: str = "passed"):
    return make_receipt(
        _config(tmp),
        ProcessResult(
            returncode=0,
            elapsed_seconds=1.0,
            timed_out=False,
            output_capped=False,
            stdout_bytes=0,
            stderr_bytes=0,
        ),
        status="completed",
        atif_scan_status=atif_status,
        assurance_status="metadata-checked",
        trajectory_digest="a" * 64 if atif_status == "passed" else None,
        atif_step_count=2 if atif_status == "passed" else None,
        atif_tool_call_count=1 if atif_status == "passed" else None,
        atif_schema_version="ATIF-v1.5" if atif_status == "passed" else None,
        runner_result=RunnerResult(
            status="completed",
            total_trials=1,
            completed_trials=1,
            errored_trials=0,
            benchmark_status="passed",
            benchmark_score=1.0,
        ),
    )


class EvidenceSummaryTests(unittest.TestCase):
    def test_completed_atif_receipt_maps_to_harness_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = receipt_to_evidence_summary(_receipt(Path(directory)))

        self.assertEqual(summary["schema_version"], "ATIF-v1.5")
        self.assertEqual(summary["trajectory_digest"], f"sha256:{'a' * 64}")
        self.assertEqual(summary["artifact_status"], "observed")
        self.assertEqual(summary["event_linkage_status"], "complete")
        self.assertEqual(summary["terminal_status"], "completed")
        self.assertNotIn("raw_trajectory", summary)
        self.assertNotIn("provider_response", summary)

    def test_missing_atif_stays_blocked_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = receipt_to_evidence_summary(
                _receipt(Path(directory), atif_status="missing")
            )

        self.assertEqual(summary["schema_version"], "ATIF-unavailable")
        self.assertEqual(summary["artifact_status"], "missing")
        self.assertEqual(summary["artifact_count"], 0)
        self.assertIsNone(summary["trajectory_digest"])
        self.assertEqual(summary["event_linkage_status"], "missing")
        self.assertEqual(summary["semantic_outcome"], "passed")

    def test_cli_projects_receipt_without_raw_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_path = root / "receipt.json"
            output_path = root / "summary.json"
            write_receipt(receipt_path, _receipt(root))

            result = main(
                [
                    "evidence-summary",
                    "--receipt",
                    str(receipt_path),
                    "--output",
                    str(output_path),
                ]
            )
            summary = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result, 0)
        self.assertEqual(summary["source_id"], "harbor")
        self.assertNotIn("prompt", summary)
        self.assertNotIn("tool_arguments", summary)
        self.assertNotIn("raw_trajectory", summary)

    def test_cli_refuses_invalid_receipt_without_echoing_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text('{"provider_response":"private"}', encoding="utf-8")

            result = main(["evidence-summary", "--receipt", str(path)])

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
