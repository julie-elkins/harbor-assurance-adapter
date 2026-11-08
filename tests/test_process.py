from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from harbor_assurance_adapter.process import missing_environment, run_bounded


class ProcessTests(unittest.TestCase):
    def test_missing_environment_detects_absent_and_empty_values(self) -> None:
        with patch.dict(
            "os.environ",
            {"PRESENT_FOR_TEST": "value", "EMPTY_FOR_TEST": ""},
            clear=True,
        ):
            self.assertEqual(
                missing_environment(
                    ("PRESENT_FOR_TEST", "EMPTY_FOR_TEST", "ABSENT_FOR_TEST")
                ),
                ("EMPTY_FOR_TEST", "ABSENT_FOR_TEST"),
            )

    def test_nonzero_exit_is_recorded_without_output_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_bounded(
                ("sh", "-c", "exit 7"),
                workdir=Path(directory),
                raw_dir=Path(directory) / "raw",
                timeout_seconds=5,
                max_output_bytes=1024,
                pass_env=(),
                path_prefix=None,
            )
            self.assertEqual(result.returncode, 7)
            self.assertFalse(result.timed_out)
            self.assertFalse(result.output_capped)

    def test_output_cap_terminates_a_chatty_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_bounded(
                ("sh", "-c", "yes x"),
                workdir=Path(directory),
                raw_dir=Path(directory) / "raw",
                timeout_seconds=5,
                max_output_bytes=1024,
                pass_env=(),
                path_prefix=None,
            )
            self.assertTrue(result.output_capped)
            self.assertIsNotNone(result.returncode)


if __name__ == "__main__":
    unittest.main()
