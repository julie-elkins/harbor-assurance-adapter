# Public study log

This log records the decisions, pivots, and verification evidence behind the
Harbor Assurance Adapter. It is deliberately written at the metadata level:
raw prompts, provider responses, credentials, tool arguments, trajectories,
and local process logs remain excluded from the public repository.

An **execution reliability** result describes whether the runner and its
environment completed the attempt. A **benchmark result** describes whether
the completed task passed verification. These are separate questions and use
separate denominators.

## 2026-11-08 — Harden provider credential transport

### Finding

The Finch compatibility shim could pass provider credentials through
process-visible command arguments. That created an unnecessary exposure risk:
local process inspection could reveal a credential even when the repository
did not contain it.

### Decision

Move `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` through a protected temporary
environment file, remove secret-valued assignments from Finch arguments, and
reject literal provider secrets in configuration.

### Instead of

Keeping secret values in the command argument vector or relying on a provider
CLI login that the non-interactive Harbor process might not inherit.

### Verification

The synthetic shim tests verify that secret values do not appear in Finch
arguments and that the temporary file is removed after the process exits.
The live Claude Code and mini-swe-agent credential-transport smoke tests
completed successfully after the change.

## 2026-11-08 — Correct the mini-swe-agent trajectory finding

### Finding

The one-task mini-swe-agent smoke completed and passed the benchmark with
native ATIF (Agent Trajectory Interchange Format) evidence. A secondary
scanner initially labelled the runner's human-readable text log as malformed
JSONL (newline-delimited JSON).

### Decision

Classify a clearly plain-text log as `metadata-unavailable`, while retaining
`metadata-invalid` for a log that identifies itself as JSONL and then contains
malformed records.

### Instead of

Weakening the native ATIF check or calling a valid run corrupted because an
optional secondary log used a different format.

### Verification

The regression test covers both formats. The change was merged in the
mini-swe-agent log-classification pull request. The raw trajectory remains
local-only.

## 2026-11-08 — Separate matched-run outcomes

### Finding

The matched Claude Code cohort produced 9 successful executions out of 10
attempts, with benchmark observations only for those completed executions.
The mini-swe-agent cohort reached terminal states for all 10 attempts but
produced no successful executions or benchmark scores.

### Decision

Report execution completion, successful execution, benchmark observation, and
benchmark pass rate separately. Do not convert provider, setup, or timeout
failures into benchmark failures.

### Instead of

Putting every attempted task in one accuracy denominator or treating a
provider refusal as evidence that the agent solved or failed the coding task.

### Verification

The existing metrics documentation defines the denominators and the public
job summarizer emits task-level execution and benchmark fields without raw
content.

## 2026-11-09 — Diagnose the mini-swe-agent comparison cohort

### Finding

Per-task artifacts from the completed cohort showed three kinds of evidence:

- provider-usage-limit evidence in 9 signals, including the timed-out
  `gpt2-codegolf` task;
- one explicit QEMU agent-setup failure;
- one agent-timeout signal.

The provider count is 9 rather than 8 because one task exposed both a provider
refusal and a timeout while Harbor was unwinding the attempt. These are
overlapping evidence signals, not disjoint task counts.

### Decision

Classify the cohort as `MixedFailures`, preserve a bounded
`failure_breakdown` in the receipt and AAH (Agent Assurance Harness)
projection, and keep `benchmark_status = "not-run"`.

### Instead of

Selecting the alphabetically first error category, which previously reported
only `AgentTimeoutError` and hid the provider-limit evidence, or selecting
only `ProviderQuotaExceeded` and hiding the setup and timeout evidence.

### Verification

The parser now returns:

```text
failure_kind = MixedFailures
failure_breakdown = {
  ProviderQuotaExceeded: 9,
  AgentTimeoutError: 1,
  AgentSetupFailure: 1
}
benchmark_status = not-run
runner_successful_trials = 0
```

The standard-library suite passes 48 tests. Category counts may sum above the
number of errored tasks because one task can expose more than one signal.

## Next controlled step

Do not rerun the ten-task mini-swe-agent cohort while the Anthropic usage limit
is active. First merge and publish the receipt-classification change. When a
funded, usable provider workspace is available, run one bounded smoke task,
verify its receipt, and only then decide whether another matched cohort is
worth its declared cost.
