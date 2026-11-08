from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from harbor_assurance_adapter.agent_trace import latest_agent_trace


class AgentTraceTests(unittest.TestCase):
    def test_in_progress_codex_trace_is_metadata_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "job" / "trial" / "agent"
            path.mkdir(parents=True)
            (path / "codex.txt").write_text(
                "\n".join(
                    [
                        json.dumps({"type": "thread.started", "secret": "hidden"}),
                        json.dumps({"type": "turn.started"}),
                        json.dumps(
                            {
                                "type": "item.started",
                                "item": {
                                    "type": "command_execution",
                                    "status": "in_progress",
                                    "command": "secret command",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = latest_agent_trace(root, time.time() - 1)

        self.assertEqual(result.status, "metadata-checked")
        self.assertEqual(result.event_count, 3)
        self.assertEqual(result.last_event_type, "item.started")
        self.assertEqual(result.last_item_type, "command-execution")
        self.assertEqual(result.last_status, "in-progress")
        self.assertIsNone(result.terminal_event_type)
        self.assertNotIn("secret", repr(result))

    def test_terminal_event_is_recorded_without_event_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "job" / "trial" / "agent"
            path.mkdir(parents=True)
            (path / "codex.txt").write_text(
                json.dumps({"type": "turn.completed", "result": "hidden"}) + "\n",
                encoding="utf-8",
            )

            result = latest_agent_trace(root, time.time() - 1)

        self.assertEqual(result.status, "metadata-checked")
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.terminal_event_type, "turn.completed")
        self.assertNotIn("hidden", repr(result))


if __name__ == "__main__":
    unittest.main()
