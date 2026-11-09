"""Typed metadata contracts for the Harbor adapter."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")
_SECRET_ENV_NAMES = frozenset({"ANTHROPIC_API_KEY", "OPENAI_API_KEY"})


def _secret_assignment_name(value: str) -> str | None:
    """Return a provider secret name when an argument contains its value."""

    candidate = value
    if value.startswith(("-e=", "--env=")):
        candidate = value.split("=", 1)[1]
    if "=" not in candidate:
        return None
    name, secret_value = candidate.split("=", 1)
    if name in _SECRET_ENV_NAMES and secret_value:
        return name
    return None


def identifier(value: object, field: str) -> str:
    """Accept a bounded identifier and reject free-form content."""

    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} must be a bounded identifier.")
    return value


def non_negative(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field} must be a non-negative number.")
    return float(value)


def positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return value


@dataclass(frozen=True)
class Budget:
    """A declared pilot ceiling and the observed values from one invocation."""

    max_total_cost_usd: float
    estimated_cost_per_task_usd: float
    task_count: int
    attempts: int
    timeout_seconds: float
    max_output_bytes: int
    stop_condition: str

    def estimated_total_cost_usd(self) -> float:
        return self.estimated_cost_per_task_usd * self.task_count * self.attempts

    def validate(self) -> None:
        if self.max_total_cost_usd <= 0:
            raise ValueError("max_total_cost_usd must be positive.")
        if self.estimated_cost_per_task_usd < 0:
            raise ValueError("estimated_cost_per_task_usd must be non-negative.")
        if self.task_count <= 0 or self.attempts <= 0:
            raise ValueError("task_count and attempts must be positive.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive.")
        if not self.stop_condition.strip():
            raise ValueError("stop_condition must not be empty.")
        if self.estimated_total_cost_usd() > self.max_total_cost_usd:
            raise ValueError(
                "declared run estimate exceeds the declared pilot ceiling; "
                "reduce tasks/attempts or raise the ceiling deliberately."
            )


@dataclass(frozen=True)
class RunConfig:
    """The pinned, metadata-only inputs for one Harbor invocation."""

    benchmark: str
    benchmark_revision: str
    agent: str
    agent_revision: str
    model: str
    provider: str
    harness: str
    harness_revision: str
    pass_env: tuple[str, ...]
    path_prefix: Path | None
    workdir: Path
    raw_run_dir: Path
    jobs_dir: Path
    command: tuple[str, ...]
    budget: Budget

    def validate(self) -> None:
        for field_name in (
            "benchmark",
            "benchmark_revision",
            "agent",
            "agent_revision",
            "model",
            "provider",
            "harness",
            "harness_revision",
        ):
            identifier(getattr(self, field_name), field_name)
        for name in self.pass_env:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", name):
                raise ValueError("pass_env contains an invalid environment name.")
        if not self.command or any(not isinstance(part, str) or not part for part in self.command):
            raise ValueError("command must contain non-empty argument strings.")
        for index, part in enumerate(self.command):
            assignment = _secret_assignment_name(part)
            if (
                assignment is None
                and part in {"-e", "--env"}
                and index + 1 < len(self.command)
            ):
                assignment = _secret_assignment_name(self.command[index + 1])
            if assignment is not None:
                raise ValueError(
                    f"command contains a literal {assignment} value; "
                    "pass the environment variable name and use pass_env instead."
                )
        if self.pass_env and self.command[0] == "harbor":
            expected_environment = (
                "harbor_assurance_adapter.harbor_environment:"
                "CredentialSafeDockerEnvironment"
            )
            if "--environment-import-path" not in self.command:
                raise ValueError(
                    "provider-backed Harbor commands must select the "
                    "argv-safe credential environment."
                )
            if expected_environment not in self.command:
                raise ValueError(
                    "provider-backed Harbor commands must select the pinned "
                    "CredentialSafeDockerEnvironment implementation."
                )
        self.budget.validate()


@dataclass(frozen=True)
class ProcessResult:
    """Bounded process facts; output content is never included."""

    returncode: int | None
    elapsed_seconds: float
    timed_out: bool
    output_capped: bool
    stdout_bytes: int
    stderr_bytes: int


@dataclass(frozen=True)
class RunReceipt:
    """A public-safe receipt for one attempted Harbor invocation."""

    schema_version: str
    run_id: str
    status: str
    benchmark: str
    benchmark_revision: str
    agent: str
    agent_revision: str
    model: str
    provider: str
    harness: str
    harness_revision: str
    command_digest: str
    task_count: int
    attempts: int
    estimated_cost_usd: float
    max_total_cost_usd: float
    elapsed_seconds: float
    returncode: int | None
    timed_out: bool
    output_capped: bool
    trajectory_store: str
    trajectory_digest: str | None
    runner_result_status: str
    runner_total_trials: int | None
    runner_completed_trials: int | None
    runner_errored_trials: int | None
    observed_cost_usd: float | None
    atif_scan_status: str
    assurance_status: str
    stop_condition: str
    assurance_source: str = "atif"
    benchmark_status: str = "not-run"
    benchmark_score: float | None = None
    benchmark_failure_kind: str | None = None
    benchmark_failure_phase: str | None = None
    atif_step_count: int | None = None
    atif_tool_call_count: int | None = None
    failure_kind: str | None = None
    failure_phase: str | None = None
    failure_breakdown: dict[str, int] | None = None
    agent_trace_status: str = "not-run"
    agent_event_count: int | None = None
    agent_tool_call_count: int | None = None
    agent_log_digest: str | None = None
    agent_last_event_type: str | None = None
    agent_last_item_type: str | None = None
    agent_last_status: str | None = None
    agent_terminal_event_type: str | None = None
    runner_successful_trials: int | None = None

    def validate(self) -> None:
        identifier(self.schema_version, "schema_version")
        identifier(self.run_id, "run_id")
        identifier(self.status, "status")
        identifier(self.benchmark, "benchmark")
        identifier(self.benchmark_revision, "benchmark_revision")
        identifier(self.agent, "agent")
        identifier(self.agent_revision, "agent_revision")
        identifier(self.model, "model")
        identifier(self.provider, "provider")
        identifier(self.harness, "harness")
        identifier(self.harness_revision, "harness_revision")
        identifier(self.command_digest, "command_digest")
        identifier(self.trajectory_store, "trajectory_store")
        identifier(self.runner_result_status, "runner_result_status")
        identifier(self.atif_scan_status, "atif_scan_status")
        identifier(self.assurance_status, "assurance_status")
        identifier(self.assurance_source, "assurance_source")
        identifier(self.benchmark_status, "benchmark_status")
        non_negative(self.estimated_cost_usd, "estimated_cost_usd")
        non_negative(self.max_total_cost_usd, "max_total_cost_usd")
        non_negative(self.elapsed_seconds, "elapsed_seconds")
        if self.task_count <= 0 or self.attempts <= 0:
            raise ValueError("task_count and attempts must be positive.")
        if self.returncode is not None and not isinstance(self.returncode, int):
            raise ValueError("returncode must be an integer or null.")
        for field_name in (
            "runner_total_trials",
            "runner_completed_trials",
            "runner_errored_trials",
            "runner_successful_trials",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or null.")
        if self.observed_cost_usd is not None:
            non_negative(self.observed_cost_usd, "observed_cost_usd")
        if self.benchmark_score is not None:
            non_negative(self.benchmark_score, "benchmark_score")
        for field_name in ("atif_step_count", "atif_tool_call_count"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} must be a non-negative integer or null.")
        for field_name in (
            "failure_kind",
            "failure_phase",
            "benchmark_failure_kind",
            "benchmark_failure_phase",
            "agent_trace_status",
            "agent_last_event_type",
            "agent_last_item_type",
            "agent_last_status",
            "agent_terminal_event_type",
        ):
            value = getattr(self, field_name)
            if value is not None:
                identifier(value, field_name)
        if self.failure_breakdown is not None:
            if not self.failure_breakdown:
                raise ValueError("failure_breakdown must not be empty.")
            for key, value in self.failure_breakdown.items():
                identifier(key, "failure_breakdown key")
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValueError(
                        "failure_breakdown values must be positive integers."
                    )
        if self.agent_event_count is not None and (
            isinstance(self.agent_event_count, bool)
            or not isinstance(self.agent_event_count, int)
            or self.agent_event_count < 0
        ):
            raise ValueError("agent_event_count must be a non-negative integer or null.")
        if self.agent_tool_call_count is not None and (
            isinstance(self.agent_tool_call_count, bool)
            or not isinstance(self.agent_tool_call_count, int)
            or self.agent_tool_call_count < 0
        ):
            raise ValueError(
                "agent_tool_call_count must be a non-negative integer or null."
            )


def command_digest(command: tuple[str, ...]) -> str:
    """Hash the argument vector without storing the command in the receipt."""

    encoded = json.dumps(list(command), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_id(config: RunConfig) -> str:
    digest = command_digest(config.command)[:16]
    return f"{config.benchmark}-{config.agent}-{digest}"


def receipt_to_dict(receipt: RunReceipt) -> dict[str, Any]:
    receipt.validate()
    return asdict(receipt)


def receipt_from_dict(value: object) -> RunReceipt:
    if not isinstance(value, dict):
        raise ValueError("receipt must be an object.")
    allowed = set(RunReceipt.__dataclass_fields__)
    unknown = set(value) - allowed
    if unknown:
        raise ValueError("receipt contains unknown fields.")
    receipt = RunReceipt(**value)
    receipt.validate()
    return receipt


def load_config(path: Path) -> RunConfig:
    """Load and validate a TOML configuration without executing anything."""

    with path.open("rb") as handle:
        data = tomllib.load(handle)
    run = data.get("run")
    budget_data = data.get("budget")
    command_data = data.get("command")
    if not isinstance(run, dict) or not isinstance(budget_data, dict) or not isinstance(command_data, dict):
        raise ValueError("config must contain [run], [budget], and [command] tables.")
    command = command_data.get("argv")
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise ValueError("[command].argv must be a list of strings.")
    config = RunConfig(
        benchmark=run["benchmark"],
        benchmark_revision=run["benchmark_revision"],
        agent=run["agent"],
        agent_revision=run["agent_revision"],
        model=run["model"],
        provider=run["provider"],
        harness=run["harness"],
        harness_revision=run["harness_revision"],
        pass_env=tuple(
            identifier(name, "pass_env name")
            for name in run.get("pass_env", [])
        ),
        path_prefix=(
            Path(run["path_prefix"])
            if run.get("path_prefix") is not None
            else None
        ),
        workdir=Path(run.get("workdir", ".")),
        raw_run_dir=Path(run.get("raw_run_dir", "runs")),
        jobs_dir=Path(run.get("jobs_dir", "jobs")),
        command=tuple(command),
        budget=Budget(
            max_total_cost_usd=non_negative(
                budget_data.get("max_total_cost_usd"), "max_total_cost_usd"
            ),
            estimated_cost_per_task_usd=non_negative(
                budget_data.get("estimated_cost_per_task_usd"),
                "estimated_cost_per_task_usd",
            ),
            task_count=positive_int(budget_data.get("task_count"), "task_count"),
            attempts=positive_int(budget_data.get("attempts"), "attempts"),
            timeout_seconds=non_negative(
                budget_data.get("timeout_seconds"), "timeout_seconds"
            ),
            max_output_bytes=positive_int(
                budget_data.get("max_output_bytes"), "max_output_bytes"
            ),
            stop_condition=identifier(
                budget_data.get("stop_condition"), "stop_condition"
            ),
        ),
    )
    config.validate()
    return config
