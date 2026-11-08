"""Metadata-only aggregation for the public evaluation study."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .receipt import read_receipt


@dataclass(frozen=True)
class ReceiptObservation:
    """A public-safe link between one task label and one local receipt."""

    agent: str
    task: str
    receipt: Path


@dataclass(frozen=True)
class AgentEvaluation:
    """Aggregate metrics with explicit denominators."""

    agent: str
    attempted_runs: int
    clean_executions: int
    benchmark_passes: int
    benchmark_observations: int
    benchmark_invalid_runs: int
    assurance_checked_runs: int
    observed_cost_usd: float

    @property
    def execution_completion_rate(self) -> float:
        return _rate(self.clean_executions, self.attempted_runs)

    @property
    def benchmark_pass_rate(self) -> float:
        return _rate(self.benchmark_passes, self.attempted_runs)

    @property
    def conditional_benchmark_pass_rate(self) -> float:
        return _rate(self.benchmark_passes, self.clean_executions)

    @property
    def benchmark_observation_rate(self) -> float:
        return _rate(self.benchmark_observations, self.clean_executions)

    @property
    def assurance_evidence_rate(self) -> float:
        return _rate(self.assurance_checked_runs, self.attempted_runs)

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = asdict(self)
        values.update(
            execution_completion_rate=self.execution_completion_rate,
            benchmark_pass_rate=self.benchmark_pass_rate,
            conditional_benchmark_pass_rate=self.conditional_benchmark_pass_rate,
            benchmark_observation_rate=self.benchmark_observation_rate,
            assurance_evidence_rate=self.assurance_evidence_rate,
        )
        return values


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _clean_execution(receipt: Any) -> bool:
    return (
        receipt.status == "completed"
        and receipt.runner_result_status == "completed"
        and receipt.runner_errored_trials == 0
        and receipt.returncode == 0
        and not receipt.timed_out
        and not receipt.output_capped
    )


def _benchmark_observed(receipt: Any) -> bool:
    return receipt.benchmark_status in {"passed", "failed", "partial"}


def _assurance_checked(receipt: Any) -> bool:
    """Recognise only explicitly labelled evidence sources."""

    if receipt.agent_trace_status != "metadata-checked":
        return False
    if receipt.assurance_source == "agent-jsonl":
        return (
            receipt.assurance_status == "metadata-checked"
            and receipt.atif_scan_status == "not-applicable"
        )
    return receipt.assurance_source == "atif" and receipt.atif_scan_status == "passed"


def aggregate_receipts(
    observations: tuple[ReceiptObservation, ...],
) -> tuple[AgentEvaluation, ...]:
    """Aggregate only fields already present in metadata-only receipts."""

    grouped: dict[str, list[Any]] = {}
    for observation in observations:
        receipt = read_receipt(observation.receipt)
        grouped.setdefault(observation.agent, []).append(receipt)

    results: list[AgentEvaluation] = []
    for agent in sorted(grouped):
        receipts = grouped[agent]
        clean = sum(_clean_execution(receipt) for receipt in receipts)
        passes = sum(receipt.benchmark_status == "passed" for receipt in receipts)
        observations_count = sum(
            _clean_execution(receipt) and _benchmark_observed(receipt)
            for receipt in receipts
        )
        invalid_runs = sum(
            receipt.benchmark_failure_kind == "VerifierEnvironmentFailure"
            for receipt in receipts
        )
        assurance = sum(_assurance_checked(receipt) for receipt in receipts)
        cost = sum(
            receipt.observed_cost_usd or 0.0
            for receipt in receipts
        )
        results.append(
            AgentEvaluation(
                agent=agent,
                attempted_runs=len(receipts),
                clean_executions=clean,
                benchmark_passes=passes,
                benchmark_observations=observations_count,
                benchmark_invalid_runs=invalid_runs,
                assurance_checked_runs=assurance,
                observed_cost_usd=cost,
            )
        )
    return tuple(results)


def load_manifest(path: Path) -> dict[str, object]:
    """Load and minimally validate the public study manifest."""

    with path.open("rb") as handle:
        manifest = tomllib.load(handle)
    study = manifest.get("study")
    metrics = manifest.get("metrics")
    agents = manifest.get("agents")
    if not isinstance(study, dict) or not isinstance(metrics, dict):
        raise ValueError("manifest must contain [study] and [metrics].")
    if not isinstance(agents, list) or not agents:
        raise ValueError("manifest must contain at least one agent.")
    if not all(isinstance(agent, dict) and isinstance(agent.get("id"), str) for agent in agents):
        raise ValueError("manifest agents must have string ids.")
    return manifest


def aggregate_to_json(observations: tuple[ReceiptObservation, ...]) -> str:
    """Serialize aggregates without including receipt paths or raw content."""

    return json.dumps(
        {"agents": [result.to_dict() for result in aggregate_receipts(observations)]},
        indent=2,
        sort_keys=True,
    )
