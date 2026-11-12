from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harbor_assurance_adapter.atif import scan_trajectory


class AtifTests(unittest.TestCase):
    def test_valid_atif_returns_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "ATIF-v1.2",
                        "steps": [
                            {"step_id": 1, "tool_calls": [{"name": "hidden"}]},
                            {"step_id": 2, "tool_calls": []},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = scan_trajectory(path)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.assurance_status, "metadata-checked")
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.tool_call_count, 1)
        self.assertEqual(result.schema_version, "ATIF-v1.2")
        self.assertIsNotNone(result.trajectory_digest)
        self.assertNotIn("hidden", repr(result))

    def test_codex_atif_v15_returns_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "ATIF-v1.5",
                        "steps": [
                            {"step_id": 1},
                            {"step_id": 2, "tool_calls": [{"name": "hidden"}]},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = scan_trajectory(path)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.assurance_status, "metadata-checked")
        self.assertEqual(result.step_count, 2)
        self.assertEqual(result.tool_call_count, 1)
        self.assertEqual(result.schema_version, "ATIF-v1.5")
        self.assertNotIn("hidden", repr(result))

    def test_missing_atif_is_not_clean(self) -> None:
        result = scan_trajectory(None)

        self.assertEqual(result.status, "missing")
        self.assertEqual(result.assurance_status, "metadata-unavailable")
        self.assertIsNone(result.trajectory_digest)

    def test_malformed_atif_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            path.write_text(
                json.dumps({"schema_version": "ATIF-v1.2", "steps": "not-a-list"}),
                encoding="utf-8",
            )

            result = scan_trajectory(path)

        self.assertEqual(result.status, "invalid")
        self.assertEqual(result.assurance_status, "metadata-refused")
        self.assertIsNotNone(result.trajectory_digest)


if __name__ == "__main__":
    unittest.main()
