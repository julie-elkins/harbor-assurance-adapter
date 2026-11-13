# Matched comparison runbook

This runbook defines the next two matched runs for the public study. A matched
run uses the same ten Terminal-Bench 2.0 task names, one attempt per task, one
concurrent task, and the same Finch compatibility shim. The purpose is to
compare runner behavior under the same task and environment conditions.

Run these from the repository root, with the provider credential already
configured in the local shell. The configurations select the repository's
argv-safe Harbor environment; do not remove that option or substitute an
older profile, because the run must not place the provider value in Docker
command arguments.

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/claude-code-comparison-10-2.0.toml --receipt runs/claude-code-comparison-10-v2.receipt.json
```

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-comparison-10-2.0.toml --receipt runs/mini-swe-agent-comparison-10-v2.receipt.json
```

After each run, create its public-safe per-task report:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance summarize-job --job JOB_DIRECTORY --receipt RECEIPT_PATH --output REPORT_PATH
```

Replace the three uppercase values with the job directory, receipt path, and
report path for that run. Do not publish the `jobs/` directory, `runs/`
directory, provider output, trajectories, prompts, or tool arguments.

The Codex reference report is the post-repair `v3` cohort. It records 10/10
clean executions, 10/10 benchmark observations, 7/10 benchmark passes, and
$10.098631 in observed Harbor cost. The earlier `v2` run remains historical
pre-repair evidence and must not be combined with `v3`.

## Credential-preflight recovery

The interrupted mini-swe-agent cohort produced four credential-preflight
failures after the Finch VM was recovered. These are not benchmark failures.
Use the separate four-task recovery profile so the adapter's bounded child
environment explicitly passes `ANTHROPIC_API_KEY` and the original diagnostic
job remains unchanged:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-credential-recovery-4-2.0.toml --receipt runs/mini-swe-agent-credential-recovery-4-v1.receipt.json
```

The recovery profile covers only `raman-fitting`, `fix-code-vulnerability`,
`regex-log`, and `sanitize-git-repo`, with one attempt per task and a declared
$60 ceiling. Its results must be reported separately from the interrupted
ten-task diagnostic and must not be spliced into that job's denominator.

## Raman unit-contract diagnostic

This is a one-task interpretation-sensitivity check: it makes the coordinate
conversion explicit through a versioned extra instruction, then compares the
result with the original `raman-fitting` failure. It is not a benchmark repair
and must not be counted as a leaderboard or matched-cohort result.

The profile has one attempt, a declared $15 ceiling, and a stop condition of
one task, any timeout, or the output cap:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-raman-unit-contract-ablation-2.0.toml --receipt runs/mini-swe-agent-raman-unit-contract-ablation-v3.receipt.json
```

The instruction is versioned at
`diagnostics/raman-unit-contract/extra-instruction.md`. Keep its receipt and
any task-level files local; publish only the metadata-only summary after the
run.

## QEMU compatibility ablation

The isolated QEMU diagnostic failed with a non-zero agent exit after the agent
extracted the Alpine kernel but omitted the known Apple-Silicon `signalfd`
compatibility shim from its final QEMU launch. The verifier could not reach the
`localhost login:` prompt. This is an agent-execution diagnostic, not a
benchmark score.

The follow-up ablation makes that compatibility condition explicit through a
versioned extra instruction. It keeps one task, one attempt, a declared $15
ceiling, and a stop condition for timeout or output cap. It is not a benchmark
repair and must not be added to a matched-cohort denominator:

```text
cd /Users/juliek/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-qemu-compatibility-ablation-2.0.toml --receipt runs/mini-swe-agent-qemu-compatibility-ablation-v1.receipt.json
```

The instruction is versioned at
`diagnostics/qemu-compatibility/extra-instruction.md`. Keep the receipt,
provider output, and trajectories local. Publish only a reviewed,
metadata-only diagnostic summary. The first ablation reached the verifier
successfully, but a later provider request failed for insufficient Anthropic
credits, so the adapter records zero clean executions and zero benchmark
observations.

After provider credits were restored, the same bounded profile completed
cleanly:

```text
cd /Users/juliek/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-qemu-compatibility-ablation-2.0.toml --receipt runs/mini-swe-agent-qemu-compatibility-ablation-v2.receipt.json
```

The `v2` result was 1/1 clean, 1/1 benchmark-observed, and 1/1 passed, at
$0.806020 observed cost. It remains a diagnostic result, not a matched
leaderboard observation. No additional paid QEMU or cohort runs are planned.
The public-safe report is
`docs/results/mini-swe-agent-qemu-compatibility-ablation-v2.json`.

## Post-bridge replication protocol

The next paid study is a replication of the post-bridge mini-swe-agent cohort.
Its question is whether the observed 10/10 clean executions and 9/10 benchmark
passes recur under the same conditions. A replication is a repeated
measurement under the same protocol; it is not a new leaderboard denominator
and it does not prove that the bridge caused the earlier improvement.

The replication keeps the following fixed:

- the same ten public task names and Terminal-Bench 2.0 revision;
- mini-swe-agent v2.4.6 and `anthropic/claude-opus-4-6`;
- one attempt per task, one concurrent task, and the same Finch compatibility
  path;
- the existing argv-safe credential environment and metadata-only receipt
  contract.

Run the one-task smoke first. It is deliberately limited to `fix-git`, a
small public task, with a declared $25 preflight ceiling:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-replication-smoke-2.0.toml --receipt runs/mini-swe-agent-replication-smoke-v1.receipt.json
```

Inspect the receipt before authorising the ten-task replication. Continue only
if the smoke is a clean execution with a valid metadata-only receipt, no
credential transport refusal, and no timeout or output-cap refusal. A clean
smoke proves the selected path is available; it does not predict the cohort
score.

The ten-task replication reuses the pinned comparison configuration so the
task set cannot drift:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance run --config config/mini-swe-agent-comparison-10-2.0.toml --receipt runs/mini-swe-agent-replication-10-v1.receipt.json
```

After the run, create its public-safe report:

```text
cd /Users/julielk/projects/harbor-assurance-adapter
uv run harbor-assurance summarize-job --job JOB_DIRECTORY --receipt runs/mini-swe-agent-replication-10-v1.receipt.json --output docs/results/mini-swe-agent-replication-10-v1.json
```

Replace `JOB_DIRECTORY` with the local Harbor job directory. Do not publish
the job directory, receipt, provider output, prompts, tool arguments, or raw
trajectories. Add the report to a separate replication manifest only after it
has been reviewed for task count, execution status, benchmark observation,
assurance evidence, and observed cost.
