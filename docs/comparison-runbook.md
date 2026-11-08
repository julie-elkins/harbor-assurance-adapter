# Matched comparison runbook

This runbook defines the next two matched runs for the public study. A matched
run uses the same ten Terminal-Bench 2.0 task names, one attempt per task, one
concurrent task, and the same Finch compatibility shim. The purpose is to
compare runner behavior under the same task and environment conditions.

Run these from the repository root, with the provider credential already
configured in the local shell:

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
