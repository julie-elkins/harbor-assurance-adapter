from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from harbor_assurance_adapter.runner_result import latest_result


class RunnerResultTests(unittest.TestCase):
    def test_harbor_trial_error_is_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "job" / "result.json"
            result_path.parent.mkdir()
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": None,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(Path(directory), time.time() - 1)
            self.assertEqual(result.status, "errored")
            self.assertFalse(result.clean)

    def test_harbor_trial_error_records_kind_and_phase(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "job" / "result.json"
            result_path.parent.mkdir()
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": 0.67,
                            "exception_stats": {
                                "NonZeroAgentExitCodeError": ["trial-1"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = latest_result(Path(directory), time.time() - 1)

        self.assertEqual(result.failure_kind, "NonZeroAgentExitCodeError")
        self.assertEqual(result.failure_phase, "agent-execution")
        self.assertEqual(result.benchmark_status, "not-run")
        self.assertIsNone(result.benchmark_score)
        self.assertEqual(result.successful_trials, 0)

    def test_nonzero_agent_exit_without_execution_is_agent_setup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "job" / "result.json"
            result_path.parent.mkdir()
            (result_path.parent / "trial-1").mkdir()
            (result_path.parent / "trial-1" / "result.json").write_text(
                json.dumps(
                    {
                        "environment_setup": {
                            "started_at": "2026-11-07T00:00:00Z",
                            "finished_at": "2026-11-07T00:00:01Z",
                        },
                        "agent_setup": {
                            "started_at": "2026-11-07T00:00:01Z",
                            "finished_at": "2026-11-07T00:00:02Z",
                        },
                        "agent_execution": None,
                    }
                ),
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": 0.0,
                            "evals": {
                                "terminal-bench": {
                                    "exception_stats": {
                                        "NonZeroAgentExitCodeError": ["trial-1"],
                                    }
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(root, time.time() - 1)

        self.assertEqual(result.failure_phase, "agent-setup")
        self.assertEqual(result.successful_trials, 0)

    def test_provider_usage_limit_is_not_agent_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "job" / "result.json"
            trial_path = result_path.parent / "trial-1"
            trial_path.mkdir(parents=True)
            (trial_path / "agent").mkdir()
            (trial_path / "agent" / "mini-swe-agent.txt").write_text(
                "provider rejected the request because the specified usage\n"
                "limits were reached",
                encoding="utf-8",
            )
            (trial_path / "result.json").write_text(
                json.dumps(
                    {
                        "agent_execution": {
                            "started_at": "2026-11-08T00:00:00Z",
                            "finished_at": "2026-11-08T00:00:01Z",
                        },
                        "exception_info": {
                            "exception_message": (
                                "provider rejected the request because the "
                                "specified usage\nlimits were reached"
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": 2.90,
                            "exception_stats": {
                                "NonZeroAgentExitCodeError": ["trial-1"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(root, time.time() - 1)

        self.assertEqual(result.failure_kind, "ProviderQuotaExceeded")
        self.assertEqual(result.failure_phase, "provider")
        self.assertEqual(result.successful_trials, 0)

    def test_provider_quota_detection_supports_claude_code_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "job" / "result.json"
            trial_path = result_path.parent / "trial-1"
            (trial_path / "agent").mkdir(parents=True)
            (trial_path / "agent" / "claude-code.txt").write_text(
                "API Error: 400 You have reached your specified "
                "API usage limits.",
                encoding="utf-8",
            )
            (trial_path / "result.json").write_text(
                json.dumps(
                    {
                        "exception_info": {
                            "exception_message": "Command failed (exit 1)",
                        },
                    }
                ),
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": 0.0,
                            "exception_stats": {
                                "NonZeroAgentExitCodeError": ["trial-1"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(root, time.time() - 1)

        self.assertEqual(result.failure_kind, "ProviderQuotaExceeded")
        self.assertEqual(result.failure_phase, "provider")

    def test_incomplete_agent_trace_is_distinguished_from_generic_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "job" / "result.json"
            trial_path = result_path.parent / "trial-1"
            (trial_path / "agent").mkdir(parents=True)
            (trial_path / "agent" / "codex.txt").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "turn.started"}),
                        json.dumps(
                            {
                                "type": "item.started",
                                "item": {
                                    "type": "command_execution",
                                    "status": "in_progress",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (trial_path / "result.json").write_text(
                json.dumps(
                    {
                        "agent_execution": {
                            "started_at": "2026-11-08T00:00:00Z",
                            "finished_at": "2026-11-08T00:00:01Z",
                        },
                        "exception_info": {
                            "exception_message": "agent process exited",
                        },
                    }
                ),
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 1,
                            "cost_usd": 0.91,
                            "exception_stats": {
                                "NonZeroAgentExitCodeError": ["trial-1"],
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(root, time.time() - 1)

        self.assertEqual(result.failure_kind, "AgentExecutionIncomplete")
        self.assertEqual(result.failure_phase, "agent-execution")

    def test_clean_harbor_result_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "job" / "result.json"
            result_path.parent.mkdir()
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 0,
                            "cost_usd": 1.25,
                            "evals": {
                                "terminal-bench": {
                                    "metrics": [{"mean": 1.0}],
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(Path(directory), time.time() - 1)
            self.assertTrue(result.clean)
            self.assertEqual(result.observed_cost_usd, 1.25)
            self.assertEqual(result.benchmark_status, "passed")
            self.assertEqual(result.benchmark_score, 1.0)

    def test_clean_execution_can_have_failed_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "job" / "result.json"
            result_path.parent.mkdir()
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 0,
                            "cost_usd": 2.0,
                            "evals": {
                                "terminal-bench": {
                                    "metrics": [{"mean": 0.0}],
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = latest_result(Path(directory), time.time() - 1)

        self.assertTrue(result.clean)
        self.assertEqual(result.benchmark_status, "failed")
        self.assertEqual(result.benchmark_score, 0.0)

    def test_verifier_environment_failure_is_not_agent_benchmark_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "job" / "result.json"
            trial_path = result_path.parent / "trial-1"
            (trial_path / "verifier").mkdir(parents=True)
            (trial_path / "verifier" / "test-stdout.txt").write_text(
                "downloading uv\n"
                "curl: (22) the requested URL returned error: 504\n"
                "uvx: command not found\n",
                encoding="utf-8",
            )
            result_path.write_text(
                json.dumps(
                    {
                        "n_total_trials": 1,
                        "stats": {
                            "n_completed_trials": 1,
                            "n_errored_trials": 0,
                            "cost_usd": 0.29,
                            "evals": {
                                "terminal-bench": {
                                    "metrics": [{"mean": 0.0}],
                                }
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = latest_result(root, time.time() - 1)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.benchmark_status, "invalid")
        self.assertIsNone(result.benchmark_score)
        self.assertEqual(result.benchmark_failure_kind, "VerifierEnvironmentFailure")
        self.assertEqual(result.benchmark_failure_phase, "verifier-setup")


if __name__ == "__main__":
    unittest.main()
