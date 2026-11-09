"""Metadata-only projection into the Agent Assurance Harness protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .receipt import read_receipt


def _event_id(scenario_id: str, suffix: str) -> str:
    digest = hashlib.sha256(f"{scenario_id}:{suffix}".encode()).hexdigest()[:16]
    return f"event-{digest}"


def _response(request: dict[str, object], receipt_path: Path | None) -> dict[str, object]:
    scenario_id = request.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id:
        return {
            "refusal": {
                "error": "invalid_request",
                "message": "scenario_id is required.",
                "guidance": "Provide the AAH synthetic scenario metadata.",
                "stage": "request",
            }
        }
    receipt = read_receipt(receipt_path) if receipt_path is not None else None
    if receipt is not None and receipt.status not in {"completed", "planned", "refused"}:
        return {
            "refusal": {
                "error": "invalid_receipt",
                "message": "receipt status is not recognized.",
                "guidance": "Provide a receipt created by this adapter.",
                "stage": "receipt",
            }
        }
    workflow_id = receipt.run_id if receipt is not None else "local-aah-check"
    assurance_status = receipt.assurance_status if receipt is not None else "synthetic"
    event_id = _event_id(scenario_id, workflow_id)
    tool_name = "receipt-present" if receipt is not None else "synthetic-contract"
    result_status = "observed" if receipt is not None else "available"
    return {
        "trace": {
            "scenario_id": scenario_id,
            "agent_id": "harbor-assurance-adapter",
            "workflow_id": workflow_id,
            "transport_status": "accepted",
            "semantic_outcome": assurance_status,
            "retry_count": 0,
            "estimated_cost_usd": receipt.estimated_cost_usd if receipt else 0.0,
            "max_retries": 0,
            "max_estimated_cost_usd": (
                receipt.max_total_cost_usd if receipt else 0.0
            ),
            "execution_status": receipt.status if receipt else "synthetic",
            "benchmark_status": receipt.benchmark_status if receipt else "synthetic",
            "benchmark_score": receipt.benchmark_score if receipt else None,
            "benchmark_failure_kind": (
                receipt.benchmark_failure_kind if receipt else None
            ),
            "benchmark_failure_phase": (
                receipt.benchmark_failure_phase if receipt else None
            ),
            "runner_total_trials": (
                receipt.runner_total_trials if receipt else None
            ),
            "runner_successful_trials": (
                receipt.runner_successful_trials if receipt else None
            ),
            "runner_errored_trials": (
                receipt.runner_errored_trials if receipt else None
            ),
            "atif_scan_status": receipt.atif_scan_status if receipt else "synthetic",
            "assurance_source": receipt.assurance_source if receipt else "synthetic",
            "atif_step_count": receipt.atif_step_count if receipt else None,
            "atif_tool_call_count": receipt.atif_tool_call_count if receipt else None,
            "failure_kind": receipt.failure_kind if receipt else None,
            "failure_phase": receipt.failure_phase if receipt else None,
            "failure_breakdown": (
                receipt.failure_breakdown if receipt else None
            ),
            "agent_trace_status": receipt.agent_trace_status if receipt else "synthetic",
            "agent_event_count": receipt.agent_event_count if receipt else None,
            "agent_tool_call_count": (
                receipt.agent_tool_call_count if receipt else None
            ),
            "agent_log_digest": receipt.agent_log_digest if receipt else None,
            "agent_last_event_type": (
                receipt.agent_last_event_type if receipt else None
            ),
            "agent_last_item_type": (
                receipt.agent_last_item_type if receipt else None
            ),
            "agent_last_status": receipt.agent_last_status if receipt else None,
            "agent_terminal_event_type": (
                receipt.agent_terminal_event_type if receipt else None
            ),
            "tool_calls": [
                {
                    "name": tool_name,
                    "result_status": result_status,
                    "result_id": event_id,
                    "source": "metadata-only",
                }
            ],
            "claim": None,
            "answer": None,
            "abstained": False,
            "abstention_reasons": [],
            "evidence_ids": [event_id],
            "side_effects": [],
            "authorization_ids": [],
            "authorization_operation_ids": [],
            "authorization_action_digests": [],
            "tool_output_flags": [
                "raw-content:excluded",
                "trajectory-store:local-only",
            ],
            "operation_ids": [],
            "idempotency_keys": [],
            "action_digests": [],
            "reconciliation_ids": [],
            "reconciliation_statuses": [],
            "policy_version": "aah-projection-v1",
            "policy_digest": hashlib.sha256(b"aah-projection-v1").hexdigest(),
            "authorization_scopes": [],
            "escalation_status": None,
            "escalation_id": None,
        },
        "events": [
            {
                "sequence": 1,
                "event_id": event_id,
                "event_type": "tool_result",
                "name": tool_name,
                "status": result_status,
                "evidence_id": event_id,
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project a local metadata receipt into AAH JSONL."
    )
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object.")
            response = _response(request, args.receipt)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            response = {
                "refusal": {
                    "error": "adapter_refusal",
                    "message": "metadata projection refused the request.",
                    "guidance": "Inspect local diagnostics; no raw content was emitted.",
                    "stage": type(error).__name__,
                }
            }
        sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0
