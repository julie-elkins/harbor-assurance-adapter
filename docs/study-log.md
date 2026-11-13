# Public study log

This log records the decisions, pivots, and verification evidence behind the
Harbor Assurance Adapter. It is deliberately written at the metadata level:
raw prompts, provider responses, credentials, tool arguments, trajectories,
and local process logs remain excluded from the public repository.

An **execution reliability** result describes whether the runner and its
environment completed the attempt. A **benchmark result** describes whether
the completed task passed verification. These are separate questions and use
separate denominators.

## 2026-11-12 — Add the receipt-to-conformance bridge

### Decision

Project validated Harbor receipts into the Agent Assurance Harness's
identifier-only ATIF evidence contract through a bounded
`evidence-summary` command. Preserve the actual ATIF schema version in the
receipt so the projection never infers a supported version.

### Instead of

Hard-coding `ATIF-v1.5`, exporting a raw trajectory, or making the Harbor
adapter import the harness as a runtime dependency.

### Why

The harness checks evidence completeness at a separate repository boundary.
The adapter already owns the local trajectory scan, digest, and bounded counts,
so the smallest safe integration is a metadata-only projection of the
validated receipt. Keeping the repositories separate also lets the harness
validate the public contract without coupling its runtime to Harbor.

### Costs if wrong

An incorrect schema version could create a false conformance pass. Exporting
raw evidence would violate the repository's public data boundary. Coupling
the runtimes would make the assurance check harder to reproduce independently.

### Verification

The adapter test suite passed all 60 tests. The cross-repository smoke passed:
a synthetic completed receipt was accepted by harness conformance, while a
planned receipt without observed ATIF evidence was blocked.

## 2026-11-12 — Verify the merged receipt-to-conformance path

### Finding

The first real post-merge one-task smoke completed cleanly on the
mini-swe-agent/Harbor/Finch path. The receipt recorded
`atif_schema_version = ATIF-v1.2`, `atif_scan_status = passed`,
63 ATIF steps, 61 tool calls, and a passing benchmark result. The projected
summary passed all five Agent Assurance Harness conformance checks.

### Decision

Treat the receipt-to-conformance bridge as verified for this pinned smoke path,
and add a synthetic checked-in contract fixture so future CI runs can detect
adapter or harness contract drift without a provider call.

### Instead of

Rerunning the ten-task cohort immediately, treating this one-task smoke as
matched benchmark evidence, or relying on a temporary local JSON file as the
only regression check.

### Why

The smoke answers the plumbing question: the merged adapter writes the actual
ATIF schema version and the harness accepts the metadata-only projection.
It does not answer the larger question of post-fix agent reliability, so a
new cohort would be a separate paid experiment.

### Costs if wrong

The smoke covers one task and one pinned runner path. The synthetic fixture
guards the public schema shape but cannot prove provider availability,
trajectory quality, or benchmark generality.

### Verification

The receipt completed in 713.054 seconds with observed cost `$1.00522975`,
one completed trial, one successful trial, zero errored trials, and benchmark
score `1.0`. The harness report accepted the summary with
`schema_version = ATIF-v1.2` and `data_boundary = metadata_only`.

## 2026-11-12 — Run the post-bridge mini-swe-agent follow-up cohort

### Finding

The same ten-task revision completed all ten executions with nine benchmark
passes. The one failure was `raman-fitting`, and the public-safe job report
classified it as `task-correctness`. Native ATIF evidence passed conformance
with `ATIF-v1.2`.

### Decision

Publish this as a separate post-fix follow-up observation: 10/10 clean
executions, 10/10 benchmark observations, 9/10 benchmark passes, and
approximately `$16.530741` observed cost.

### Instead of

Replacing the original 9/10 execution and 6/10 pass result, combining the two
cohorts into one denominator, or claiming that the evidence bridge itself
caused the higher score.

### Why

The task-set revision and model match the historical mini-swe-agent cohort,
which makes the follow-up useful for measuring changed observed reliability.
It is still a new run with new provider and environment conditions, so the
result supports a follow-up comparison but not a causal attribution.

### Costs if wrong

Overstating the improvement would turn a single follow-up into a universal
model claim. Under-reporting it would hide the useful finding that the
credential and evidence path now completed all ten executions.

### Verification

The public-safe report records 9/10 passes, 10/10 clean executions,
`benchmark_observation_rate = 1.0`, `atif_scan_status = passed`, and
`assurance_source = atif`. The harness conformance report accepted all five
metadata checks.

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

## 2026-11-10 — Isolate the completed-cohort credential recovery

### Finding

The interrupted mini-swe-agent cohort reached a terminal result with four
credential-preflight `ValueError` records. Harbor's standalone `job resume`
path did not provide a reliable recovery boundary: it bypassed the adapter's
credential allow-list, and filtering a completed job removed trial directories
without producing replacement executions.

### Decision

Create a separate four-task recovery profile and run it through
`uv run harbor-assurance run`. The profile covers only
`raman-fitting`, `fix-code-vulnerability`, `regex-log`, and
`sanitize-git-repo`, with one attempt per task, a $40 estimate, and a $60
declared ceiling.

### Instead of

Rerunning all ten tasks, mutating the original terminal job, or treating the
four preflight failures as benchmark failures.

### Why

The adapter entry point explicitly passes only the named provider credential
into the bounded Harbor child process and retains the argv-safe Harbor
environment hook. A new job identity keeps recovery evidence separate from
the interrupted diagnostic denominator and limits additional paid work to the
invalid attempts.

### Costs if wrong

The recovery run can establish whether the four tasks were blocked only by
credential transport; it cannot repair the original cohort's timeouts or
retroactively make that cohort matched. Publishing the recovery as a second
ten-task result would overstate the evidence.

### Verification

Validate the new configuration with the standard test suite and a dry run
before starting the paid recovery. Generate a separate metadata-only report
after completion.

### Result

The recovery completed with 4/4 clean executions, 4/4 benchmark observations,
3/4 benchmark passes, a 1.0 execution completion rate, a 1.0 benchmark
observation rate, and observed cost of `3.444659` USD. ATIF (Agent Trajectory
Interchange Format, the structured execution trace) metadata passed for the
run. The only benchmark failure was `raman-fitting`, classified as
task-correctness rather than credential or infrastructure failure.

The public-safe report is
`docs/results/mini-swe-agent-credential-recovery-4-v1.json`.

### Decision

Treat the repaired credential path as execution-verified for this bounded
mini-swe-agent/Finch/Harbor recovery. Keep the four-task recovery separate
from the interrupted ten-task diagnostic and do not splice its 3/4 score into
the ten-task denominator.

## 2026-11-10 — Investigate the `raman-fitting` failure

### Finding

The `raman-fitting` attempt was a clean execution but a benchmark failure:
the agent created the required result file, while the verifier rejected both
peak parameter sets. This is a task-correctness result—whether the completed
output satisfies the task's semantic requirements—not an execution-reliability
or credential-transport failure.

The local diagnostic record shows that the agent considered applying an
instrument-axis calibration, then submitted the fit in the data's native
axis. The pinned task verifier and reference solution instead assume a
calibrated Raman-shift axis. The task instruction does not state that unit
conversion or axis contract explicitly, so the benchmark task is
under-specified even though the verifier's outcome is unambiguous.

### Decision

Keep the observed result as one benchmark failure in the bounded recovery
cohort, and classify its cause as task-correctness with task-contract
ambiguity. Do not change the verifier, relabel the failure as infrastructure,
or use a calibration hint to create a matched leaderboard score.

### Instead of

Retrying the provider, changing credential transport, editing the benchmark
verifier, or rerunning the task with an extra instruction and presenting that
diagnostic result as if it were the original benchmark condition.

### Why

The runner completed the task, the result file existed, and the verifier ran
to a normal assertion failure. That establishes that the infrastructure path
worked. The task's missing unit contract explains why an agent can identify a
plausible calibration path yet still choose an interpretation that the
verifier rejects.

### Costs if wrong

Calling this an infrastructure failure would hide a real output-quality issue.
Calling it only an agent failure would hide a benchmark-design issue. Changing
the task or mixing calibration-guided reruns into the public score would
invalidate the comparison by changing the evaluated condition.

### Verification

The classification is supported by the completed trial metadata, the
verifier's normal two-assertion failure, the pinned task fixture, and the
corresponding reference path. Raw task data, prompts, provider responses, and
trajectories remain local-only.

## 2026-11-10 — Validate the Raman unit-contract ablation

### Result

After replacing the ineffective skill injection with a direct extra
instruction, the one-task ablation completed cleanly and passed all three
verifier tests. The instruction appeared in the captured task prompt, and the
agent converted the coordinate system before fitting.

The metadata-only result was:

- 1/1 clean execution
- 1/1 benchmark observation
- 1/1 benchmark pass
- ATIF (Agent Trajectory Interchange Format, the structured execution trace)
  metadata passed
- observed cost of `0.198360` USD

### Decision

Treat this as evidence that the missing unit contract was causally relevant to
the original Raman failure: once the conversion was explicitly delivered, the
same agent and pinned task passed. Keep it labelled as a diagnostic ablation,
not as a leaderboard or matched-cohort score.

### Instead of

Editing the Terminal-Bench task or verifier, replacing the original failed
observation, or adding the ablation pass to the ten-task comparison.

### Why

The benchmark revision, task, model, runner, and credential transport stayed
constant. The controlled change was the instruction boundary, and the local
evidence confirms that the added instruction reached the agent before the
successful fit.

### Costs if wrong

The ablation changes the agent's prompt, so treating its 1/1 result as a
matched leaderboard result would overstate the original condition. The result
supports a causal explanation for this task; it does not establish that every
under-specified benchmark task will respond the same way.

### Verification

The public-safe report is
`docs/results/mini-swe-agent-raman-unit-contract-ablation-v3.json`. The
receipt records one completed trial, one benchmark pass, ATIF metadata
success, and observed cost of `0.198360` USD. Raw task data, prompts,
provider responses, and trajectories remain local-only.

### Next controlled step

If we want to measure recoverability, run a separately labelled one-task
diagnostic ablation with the unit contract made explicit. Report it as an
interpretation-sensitivity check, not as a leaderboard or matched-cohort
result. Do not spend that additional provider budget unless the diagnostic
question is worth answering.

## 2026-11-10 — Provider-credit refusal of the Raman ablation

### Finding

The unit-contract ablation did not reach model execution. Anthropic rejected
the request because the account balance was too low. The adapter recorded a
provider-backed agent exit, no benchmark result, no output file, and
`0.0` observed provider cost.

### Decision

Exclude this attempt from both task-correctness and interpretation-sensitivity
analysis. It is provider-quota evidence only; it does not confirm or
disconfirm whether the explicit unit contract helps the agent.

### Instead of

Retrying repeatedly, treating the refusal as a Raman failure, changing the
unit-contract skill, or changing credential transport.

### Why

The credential reached the provider boundary, but the provider refused before
the agent could work. The verifier therefore ran against no result file, and
the zero reward is not a meaningful benchmark observation.

### Costs if wrong

Counting this as an ablation failure would understate the agent's task
performance and conflate account state with the experimental instruction.
Repeated retries would add no evidence while the provider balance remains
insufficient.

### Verification

The metadata-only receipt records `benchmark_status = not-run`,
`observed_cost_usd = 0.0`, and an agent-execution refusal. The local trial
record contains the provider's insufficient-credit response; that response
and all raw logs remain local-only.

### Next controlled step

After the Anthropic account has usable credit, rerun the exact committed
ablation once. Do not alter the config or skill between attempts, so the next
result remains comparable to the recorded experiment definition.

## 2026-11-10 — Correct the Raman ablation instruction boundary

### Finding

The first funded ablation completed cleanly but did not receive its treatment:
Harbor recorded the injected skill in job metadata, while the mini-swe-agent
adapter did not register `skills_dir` or append the skill text to the task
instruction. The trajectory therefore contained the original task only, and
the agent again submitted native-axis values.

### Decision

Replace the ineffective skill injection with Harbor's
`--extra-instruction-path`, which appends a versioned diagnostic instruction
directly to the task prompt. Treat the funded `v2` attempt as an invalid
ablation and exclude it from interpretation-sensitivity analysis.

### Instead of

Calling `v2` evidence that the unit contract did not help, changing the
benchmark verifier, or repeating the same ineffective skill configuration.

### Why

The experiment must verify that the treatment reached the agent before
interpreting its outcome. The job lock proves the skill was selected, but the
captured mini-swe-agent task prompt contains no unit-contract text. The
extra-instruction path is the smallest supported boundary that directly
changes the instruction mini-swe-agent receives.

### Costs if wrong

Counting `v2` as a failed ablation would produce a false causal conclusion.
Using the skill path again would spend another provider call without testing
the intended intervention.

### Verification

The corrected configuration is tested for the extra-instruction path and the
instruction text. The next run must be checked for the appended text in the
local task/trajectory evidence before its benchmark outcome is interpreted.

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

## 2026-11-10 — Freeze and publish the public study summary

### Decision

Freeze the paid-run evidence and publish a metadata-only summary covering the
matched Codex and mini-swe-agent cohorts, the Raman unit-contract diagnostic,
the post-hardening execution diagnostic, and the assurance finding.

### Instead of

Starting another full provider-funded cohort before publication, combining
Claude's partial or diagnostic runs with the matched denominator, or presenting
the Raman ablation as leaderboard evidence.

### Why

The existing evidence is sufficient to explain execution reliability,
benchmark correctness, and evidence completeness as separate dimensions. The
Raman ablation answered its causal question at one-task scope, while the
remaining Claude evidence is not a clean comparable ten-task report.
Publishing now preserves the exact denominators and prevents later runs from
silently changing the public claim.

### Verification

The summary links the public per-run reports and states the non-claims. The
standard-library suite passes all 56 tests, all public JSON files parse, and
the Raman runbook points to the valid `v3` receipt rather than the provider-
refused `v1` attempt.

### Next step

Review the publication branch, then merge it before drafting the external
leaderboard or LinkedIn comment. Keep that comment draft-only until Julie
chooses the final wording.

## 2026-11-13 — Add the offline cohort comparator

### Decision

Add a local `compare-cohorts` command that validates the saved public
`job-evaluation-v1` reports against their pinned configurations, recomputes
execution and benchmark metrics from task records, and emits task-level deltas
without making provider calls. Use the original mini-swe-agent cohort as the
baseline so the post-bridge change is directly visible.

### Instead of

Manually copying aggregate values into a study table, comparing raw
trajectories, or treating the post-bridge cohort as a new leaderboard
denominator.

### Why

The public task summaries contain enough metadata to check reproducibility
without exposing prompts, provider responses, credentials, or trajectories.
Fail-closed validation catches stale aggregates, mismatched task-set
revisions, model/config drift, and unequal task sets before a public result is
used.

### Verification

The real manifest validated the original mini-swe-agent cohort, Codex, and the
post-bridge mini-swe-agent cohort. The generated report preserves the known
results: 9/10 clean and 6/10 passed for the original mini-swe-agent cohort,
10/10 clean and 7/10 passed for Codex, and 10/10 clean and 9/10 passed for the
post-bridge mini-swe-agent cohort. All 63 standard-library tests passed.

### Next step

Review the staged diff and publish the comparator, manifest, checked-in
comparison report, tests, and documentation. Do not start another paid cohort
until a distinct measurement question is defined.
