"""Protect the CI reproducibility gate's offline and credential-free boundary."""

from pathlib import Path
import unittest


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "reproducibility.yml"
)


class CIWorkflowTests(unittest.TestCase):
    def test_workflow_runs_locked_tests_and_offline_comparison(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        for required in (
            "permissions:\n  contents: read",
            "persist-credentials: false",
            "uv sync --locked",
            "uv run python -m unittest discover -s tests -v",
            "uv run harbor-assurance compare-cohorts",
            "--manifest docs/cohort-comparison.toml",
            "--output /tmp/cohort-comparison-v1.json",
            "cmp --silent /tmp/cohort-comparison-v1.json docs/results/cohort-comparison-v1.json",
        ):
            self.assertIn(required, workflow)

    def test_workflow_cannot_start_live_provider_execution(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")

        for provider_key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            self.assertNotIn(provider_key, workflow)
        self.assertNotIn("harbor-assurance run", workflow)
        self.assertNotIn("harbor run", workflow)


if __name__ == "__main__":
    unittest.main()
