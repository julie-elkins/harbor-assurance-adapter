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
