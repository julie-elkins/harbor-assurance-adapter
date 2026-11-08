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
        self.assertEqual(result.tool_call_count, 0)
        self.assertIsNotNone(result.log_digest)
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
        self.assertEqual(result.tool_call_count, 0)
        self.assertEqual(result.terminal_event_type, "turn.completed")
        self.assertNotIn("hidden", repr(result))

    def test_claude_tool_calls_are_counted_without_exporting_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "job" / "trial" / "agent"
            path.mkdir(parents=True)
            (path / "claude-code.txt").write_text(
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "thinking", "text": "hidden"},
                                {"type": "tool_use", "name": "Bash", "input": "hidden"},
                            ]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = latest_agent_trace(root, time.time() - 1)

        self.assertEqual(result.status, "metadata-checked")
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.tool_call_count, 1)
        self.assertNotIn("hidden", repr(result))

    def test_malformed_jsonl_is_not_assurance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "job" / "trial" / "agent"
            path.mkdir(parents=True)
            (path / "claude-code.txt").write_text(
                '{"type":"result"}\nnot-json\n',
                encoding="utf-8",
            )

            result = latest_agent_trace(root, time.time() - 1)

        self.assertEqual(result.status, "metadata-invalid")
        self.assertIsNotNone(result.log_digest)

    def test_plain_text_agent_log_is_not_claimed_as_malformed_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "job" / "trial" / "agent"
            path.mkdir(parents=True)
            (path / "mini-swe-agent.txt").write_text(
                "Task completed in the runner's human-readable log.\n",
                encoding="utf-8",
            )

            result = latest_agent_trace(root, time.time() - 1)

        self.assertEqual(result.status, "metadata-unavailable")
        self.assertIsNotNone(result.log_digest)


if __name__ == "__main__":
    unittest.main()
