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

## 2026-11-09 — Close the Harbor-to-shim credential gap

### Finding

The first transport hardening change removed provider values from Finch
arguments, but Harbor v0.9.0 still rendered the agent's per-command
environment as Docker `-e NAME=value` arguments. Local process inspection
therefore exposed a second copy of the credential before the Finch shim
received it.

### Decision

Use Harbor's custom environment hook for every provider-backed profile.
`CredentialSafeDockerEnvironment` removes secret values before Docker
argument construction, transfers them through a temporary path-only copy,
and loads them inside the container shell. Configuration validation refuses
provider-backed Harbor commands that do not select this environment.

### Instead of

Relying on the Finch shim alone, because that protects only the downstream
runtime boundary after Harbor has already created the Docker command.

### Why

The exposure was at the Harbor-to-Docker boundary, not the Docker-to-Finch
boundary. Fixing the shared Harbor environment method closes the source of
the leak while preserving the agent's expected environment variables inside
the container.

### Costs if wrong

The custom environment is coupled to Harbor's supported import hook and
Docker environment interface. A Harbor upgrade could change that interface,
so the import smoke and synthetic transport tests must run before any paid
cohort. A failed import must block the run rather than fall back silently to
the older transport.

### Decided by

Julie and Codex, after tracing Harbor's Docker `exec` construction and the
local process inspection evidence on 2026-11-09.

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

## 2026-11-09 — Run the quota-unblocked mini-swe-agent cohort

### Finding

The post-limit one-task smoke proved that the provider and execution path were
available, although the smoke task itself failed benchmark verification. The
ten-task cohort then reached 10/10 terminal states with no provider-quota
refusals.

### Result

Nine of 10 tasks were clean executions. All nine produced benchmark
observations; six passed and three failed task verification. One task,
`qemu-startup`, failed during agent setup and was excluded from the benchmark
accuracy denominator.

The public metrics are:

```text
execution_completion_rate = 9/10 = 0.90
benchmark_observation_rate = 9/9 = 1.00
conditional_benchmark_pass_rate = 6/9 = 0.6667
overall_attempted_task_pass_rate = 6/10 = 0.60
observed_cost_usd = 16.182813
```

### Decision

Publish the public-safe per-task report at
`docs/results/mini-swe-agent-comparison-10-v3.json`, and report the QEMU
setup failure separately from benchmark correctness.

### Instead of

Calling the cohort a 10/10 accuracy result, counting the setup failure as a
benchmark failure, or rerunning successful tasks.

### Verification

The receipt records `runner_completed_trials = 10`,
`runner_successful_trials = 9`, `runner_errored_trials = 1`,
`benchmark_status = "not-run"` at the aggregate receipt level because Harbor
was not completely clean, and `atif_scan_status = "passed"`. The public job
summarizer recovers the valid per-task benchmark observations without
publishing raw execution content.

### Next investigation

Diagnose the isolated `qemu-startup` agent-setup failure before treating this
cohort as a fully clean matched comparison. The current result is already
valid evidence for partial execution reliability and conditional benchmark
performance.

## 2026-11-09 — Diagnose the mini-swe-agent qemu-startup setup failure

### Finding

The `qemu-startup` trial did not reach model execution or benchmark
verification. Harbor's agent setup (installing the runner before it starts)
failed while running mini-swe-agent's root package command:

```text
apt-get update && apt-get install -y curl build-essential git
```

The cached public image is Debian Bullseye. A local Finch reproduction against
the same image showed that the live `bullseye-security` mirror returned HTTP
404 errors for advertised package versions, including packages needed by
`curl`, `git`, and their dependencies. This is a package-source compatibility
failure, not evidence that the model failed the QEMU task.

### Decision

Extend the existing bounded Bullseye archive fallback in `bin/docker` to cover
mini-swe-agent's exact package set, then verify the rewritten command with a
synthetic shim test and one isolated setup smoke before considering a rerun of
the matched cohort.

### Instead of

Rerunning the ten-task cohort unchanged, counting `qemu-startup` as a benchmark
failure, or changing the public task image and package set.

### Why

The unmodified command failed reproducibly with package-download 404s. The
same command succeeded in the identical image when only the stale security
mirror was replaced with Debian's archive and APT's expired-index check was
disabled. A bounded rewrite preserves the task image and requested packages
while addressing the observed failure mechanism.

### Costs if wrong

The fix could mask a different package-install problem if the original
failure was transient. To control that risk, the next verification must prove
both the command rewrite and an end-to-end isolated setup; no leaderboard claim
will be revised from this diagnosis alone.

### Verification

The unmodified setup exited 100 with multiple security-mirror 404s. The
archive-fallback setup installed all requested packages successfully. No
provider call or paid model execution was used for this reproduction.

## 2026-11-09 — Implement the bounded mini-swe-agent setup repair

### Change

The Finch/Docker shim now recognizes only the two known Harbor setup package
commands: Codex's `curl ripgrep` set and mini-swe-agent's
`curl build-essential git` set. It prefixes a small shell function that applies
the Bullseye archive fallback only when the image declares
`bullseye-security`; other package commands pass through unchanged.

The reproducible one-task profile is
`config/mini-swe-agent-qemu-setup-smoke-2.0.toml`.

### Verification

The shell syntax check passed, and the standard-library suite passed all 48
tests. The shim regression test verifies both supported package sets and
verifies that an unrelated `curl git` command is not rewritten. A direct
Finch run of the exact archive-fallback setup against
`alexgshaw/qemu-startup:20251031` installed all requested packages.

At this implementation checkpoint, the end-to-end Harbor smoke had not started
because `ANTHROPIC_API_KEY` was absent from both the current and login-shell
environments. No provider call or paid model execution had yet been made; the
subsequent validation is recorded below.

### Next gate

Load the already-authorized Anthropic credential into the local shell, run the
one-task mini-swe-agent qemu setup smoke, and inspect its receipt. Only a clean
setup and agent execution should justify considering another matched cohort.

## 2026-11-09 — Validate the mini-swe-agent setup repair

### Result

The isolated mini-swe-agent `qemu-startup` smoke completed successfully after
the shim update. Agent setup completed, the agent executed the task, and the
Terminal-Bench verifier returned a passing score:

```text
runner_successful_trials = 1
runner_errored_trials = 0
benchmark_status = passed
benchmark_score = 1.0
atif_scan_status = passed
atif_step_count = 74
atif_tool_call_count = 72
observed_cost_usd = 1.306460
```

### Decision

Treat the Bullseye package-source compatibility issue as repaired for this
runner/image path. Keep the original ten-task v3 report unchanged and retain
the smoke as separate diagnostic evidence.

### Instead of

Retroactively changing the v3 cohort from 9/10 clean executions to 10/10, or
rerunning the entire cohort solely to replace one setup failure.

### Why

The targeted smoke proves that the exact failed task can now pass through
environment setup, mini-swe-agent execution, verification, and the metadata
assurance scan. It does not prove that the historical cohort was run under the
same shim, so changing its denominator would make the public study less
reproducible.

### Verification

The receipt is
`runs/mini-swe-agent-qemu-setup-smoke-v1.receipt.json`. The per-task result
contains a normal agent result, a passing verifier result, and no exception.
The original v3 report remains a historical pre-fix cohort result; the smoke
is a post-fix diagnostic confirmation.

### Next step

Review and publish the shim, test, profile, and study-log changes. After that,
decide whether a fresh full matched cohort is worth its provider cost.

## 2026-11-09 — Review the post-hardening mini-swe-agent follow-up

### Result

The follow-up ten-task run reached all ten terminal states, but two tasks
errored. The metadata receipt classified the run as `MixedFailures` and
preserved these overlapping signals:

```text
runner_completed_trials = 10
runner_successful_trials = 8
runner_errored_trials = 2
execution_completion_rate = 8/10 = 0.80
failure_breakdown = {
  AgentTimeoutError: 2,
  ProviderQuotaExceeded: 1
}
benchmark_status = not-run
atif_scan_status = passed
observed_cost_usd = 23.244097
```

The provider-quota count is a signal count, not a task count. One errored task
can expose more than one failure signal while Harbor is unwinding the attempt.
The public aggregate report is
`docs/results/mini-swe-agent-comparison-10-v4.json`.

### Decision

Treat v4 as diagnostic evidence about execution reliability, not as a
benchmark comparison result. Do not calculate an accuracy score from this
receipt, and do not attribute the timeout signals to the credential transport
without task-level evidence.

### Instead of

Calling the run an 8/10 benchmark result, converting the two errored tasks into
benchmark failures, or treating the presence of a provider-quota signal as
proof that the new transport hook caused the failure.

### Why

The runner was not clean, so the adapter correctly withheld the aggregate
benchmark score. The ATIF (Agent Trajectory Interchange Format, the structured
execution trace) metadata check passed, which confirms that assurance metadata
was recorded, but it does not establish task correctness or provider health.

### Costs if wrong

Keeping v4 diagnostic-only means it contributes an execution-reliability
observation but not a leaderboard accuracy number. That is less visually
complete, but publishing an unsupported score would make the public study
misleading.

### Next controlled step

Revoke the previously exposed Anthropic key and load a newly issued key.
Before another paid cohort, run one bounded mini-swe-agent smoke with the
argv-safe environment hook, inspect the receipt, and verify through local
process inspection that the secret is absent from Harbor, Docker, and Finch
argument vectors. Only a clean post-rotation smoke should be treated as live
verification of the credential remediation. A new ten-task cohort remains
optional and should wait until the smoke is clean.

## 2026-11-09 — Diagnose the post-rotation credential smoke

### Finding

The post-rotation one-task smoke did not reach model execution. Harbor's
`CredentialSafeDockerEnvironment` created the temporary credential file under
`/tmp`, but Finch's Docker Compose copy boundary reported that the source file
did not exist. The receipt recorded one `RuntimeError`, no provider cost, no
ATIF (Agent Trajectory Interchange Format, the structured execution trace)
artifact, and no benchmark result.

### Decision

Create the temporary file in Finch's host-visible `/private/tmp` directory
when available, close the file before invoking Docker Compose, keep the path
alive until the upload returns, and delete it in a deterministic cleanup
block.

### Instead of

Retrying with the rotated key, weakening the argv-safe transport, or treating
the runtime error as an Anthropic quota refusal.

### Why

The failure occurred while copying the file into the container, before the
agent received the credential and before a provider request could be priced.
The key rotation therefore remains valid; the transport implementation was the
blocking defect.

### Verification

The regression test verifies the Finch-visible path, mode `0600`, exact
secret-file contents, and cleanup after the upload context exits. A new
non-paid synthetic boundary probe and one bounded post-fix smoke are required
before calling the credential remediation live-verified.

## 2026-11-09 — Validate the repaired credential transport

### Result

The bounded post-fix mini-swe-agent smoke completed successfully with the
rotated Anthropic credential:

```text
runner_completed_trials = 1
runner_successful_trials = 1
runner_errored_trials = 0
benchmark_status = passed
benchmark_score = 1.0
atif_scan_status = passed
atif_step_count = 105
atif_tool_call_count = 103
observed_cost_usd = 9.449655
```

The public-safe diagnostic report is
`docs/results/mini-swe-agent-credential-transport-post-fix-v2.json`.

### Decision

Treat the credential transport as live-smoke-verified for this
mini-swe-agent/Finch/Harbor path. Keep this one-task result separate from the
historical and matched ten-task cohorts.

### Instead of

Calling the transport fully proven across every Harbor version, container
image, provider, or agent, or adding this smoke to a ten-task accuracy
denominator.

### Why

The smoke demonstrates a real agent execution, benchmark verification, and
ATIF (Agent Trajectory Interchange Format, the structured execution trace)
metadata capture after the transport repair. It is still one task on one
runner path, so it proves the repaired path works but does not establish
general cross-environment coverage.

### Next controlled step

Review, stage, commit, and publish the transport fix, tests, documentation,
and the two public-safe diagnostic reports. After that, run the optional fresh
mini-swe-agent ten-task cohort only if the additional provider cost is worth
measuring post-fix execution reliability.
