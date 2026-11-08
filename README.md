# Harbor Assurance Adapter

This repository runs a bounded Harbor benchmark invocation and records a
metadata-only receipt for the Agent Assurance Harness (AAH), the secondary
assurance check.

The benchmark answers whether the coding task passed. AAH checks whether the run
can make a bounded, observable, privacy-safe claim about what happened. Keeping
those results separate prevents a good task score from hiding an unverifiable run.
The receipt therefore records execution status separately from benchmark status:
`completed` means Harbor finished cleanly, while `passed`, `failed`, or `partial`
describes the benchmark score.

The evaluation layer reports execution completion, benchmark correctness,
conditional benchmark pass rate, benchmark observation rate, assurance evidence,
and observed cost separately. A conditional pass rate is the fraction of clean
executions that passed verification; it is not a replacement for the overall
pass rate.

## Current scope

- First runner: mini-swe-agent v2.4.6.
- Second runner: Claude Code 2.1.319 through Harbor's built-in `claude-code`
  agent.
- Third runner: Codex npm package 0.167.0 through Harbor's built-in `codex`
  agent.
- Evaluation target: a matched 10-task public Terminal-Bench 2.0 cohort.
- Public study contract: [evaluation-manifest.toml](docs/evaluation-manifest.toml)
  and [metrics.md](docs/metrics.md).
- Matched-run procedure:
  [comparison-runbook.md](docs/comparison-runbook.md).
- Public per-task results are generated with the `summarize-job` command and
  stored under `docs/results/`.
- Raw trajectories and process logs: local-only under `runs/`.
- Public receipt: identifiers, versions, counts, statuses, digests, timing, and
  declared cost observations only.
- Pilot runs and matched comparison runs remain separate evidence sets; a
  follow-up task must not be added to a leaderboard-style denominator.

## Assurance finding: benchmark success is not trajectory evidence

We verified that a successful benchmark run did not automatically guarantee
that the expected trajectory artifact was present. In a controlled Claude Code
smoke run, the agent produced a complete local JSONL event log, but Harbor did
not produce an ATIF trajectory file. The assurance adapter detected the
discrepancy, refused to mislabel the run as ATIF-verified, and added an
explicitly labelled fallback path for the available event-log metadata.

This finding demonstrates the value of testing the evidence pipeline separately
from benchmark scoring: a task can pass while the execution evidence contract
is incomplete. The adapter keeps the raw log local and publishes only bounded
metadata such as event counts, tool-call counts, statuses, and digests.

The declared cost is a preflight estimate, not a provider billing guarantee.
The command is never run until the estimate is within the configured ceiling.

## Validate without executing

```bash
uv run harbor-assurance run \
  --config config/mini-swe-agent-smoke.toml \
  --receipt /tmp/harbor-assurance-planned.json \
  --dry-run
```

The example configuration intentionally contains model, provider, benchmark, and
Harbor-release placeholders. Replace them with exact pinned values before a live
run. “Pinned” means recorded to an exact release or commit so another person can
reproduce the invocation.

## Live-run prerequisites

Harbor needs a running Docker-compatible sandbox. Docker Desktop is not installed
on this Mac; Finch is the local runtime and its VM must be running before the
live run. The repository includes a local `docker` shim that forwards Harbor's
Docker and Compose calls to Finch and translates the small set of Harbor Compose
flags Finch does not implement; this is a compatibility adapter, not a change to
Harbor.

The current Harbor registry publishes `terminal-bench@2.0`, not `2.1`. The
configuration keeps `2.1` as the intended leaderboard target so we do not claim
that a `2.0` smoke result is equivalent. The passing `nop` smoke uses `2.0` only
to prove the local container path.

The Finch shim also adds the `mcp` Python package to mini-swe-agent's isolated
`uv` tool environment. This is a compatibility repair for the current LiteLLM
dependency path: LiteLLM imports MCP support at startup, while mini-swe-agent
does not declare MCP as a required dependency. It does not modify Harbor, the
benchmark image, or the task verifier.

For the public Terminal-Bench tasks whose verifier script installs `uv` at
test time, the shim routes the pinned `uv` 0.9.5 installer artifact through the
Astral release mirror. This is a dependency-transport repair for transient
GitHub download failures; it leaves the verifier script, pinned test
dependencies, and scoring logic unchanged.

For Codex setup on Debian-based task images, the shim adds bounded APT archive
retries. APT is the Debian package manager. The public `qemu-startup` task uses
old Bullseye metadata whose live security mirror points at removed package
archives, so the shim uses Debian's matching archive only when
`bullseye-security` is present. It does not add packages or change the task
image.

For provider secrets, the shim writes a user-readable-only temporary `env_file`
and uses Finch's direct `exec --env-file` path for agent commands. This applies
to both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`, including direct
Docker-compatible `exec`, `run`, and `create` paths. The value therefore stays
out of the Finch process command line, where local process inspection tools
could otherwise see it. Other Harbor execution variables remain on the direct
exec command because they contain control flags, not credentials.

The adapter also rejects a configuration that embeds a literal provider secret
in its command argument vector, called `argv` (the process-visible argument
list). Credentials must arrive through the named `pass_env` allow-list instead.
The shim removes secret-valued environment assignments before launching Finch,
creates a protected temporary file, and deletes it when the Finch process exits.

The selected model provider also needs a locally configured credential. Do not put
the credential in this repository or send it in chat. The Harbor process receives
only the provider environment variable required by the selected agent, after its
name is added to the configuration's `pass_env` allow-list. An allow-list is an
explicit list of names permitted through a boundary; all other environment
variables remain excluded.

Before starting Harbor, the adapter checks that every allowed credential
variable is present and non-empty. A missing credential produces a structured
refusal with zero observed cost and no Harbor subprocess, so an authentication
mistake is not misclassified as agent-execution unreliability.

The real smoke run still requires a locally configured provider credential and
exact `model` and `provider` identifiers. The no-model Harbor/Finch path has
already been validated with one `terminal-bench@2.0` task.

The prepared live configuration is
`config/mini-swe-agent-live-2.0.toml`. It passes only `ANTHROPIC_API_KEY` to
the Harbor subprocess and limits the first paid run to one task and one attempt.
It also sets Harbor's agent-timeout multiplier to `4`: Harbor's default
900-second agent limit becomes 3600 seconds, matching the adapter's declared
wall-clock budget. The $5 estimate is deliberately conservative; it is a
stop-condition estimate, not a provider billing guarantee.

The second comparison profile is
`config/claude-code-live-2.0.toml`. Harbor installs Claude Code at the pinned
2.1.319 release, limits the agent to a declared $15 per-task budget, and emits
the same metadata-only receipt contract. The adapter records native ATIF
(Agent Trajectory Interchange Format) evidence when Harbor produces it and
uses an explicitly labelled JSONL event-log source when ATIF is absent. The
profile has been validated locally and has completed controlled tasks under
both evidence conditions.

The third comparison profile is `config/codex-live-2.0.toml`. It passes only
`OPENAI_API_KEY` to Harbor, pins the published Codex npm release `0.167.0`,
uses `openai/gpt-5.5` with high reasoning effort, and limits the first
comparison to one task and one attempt. The local Codex build reported
`0.167.0.932`, but that is not a valid npm install version; the Harbor profile
records the package version it can actually install. A Codex CLI login is not
automatically the same thing as API-key authentication for this non-interactive
Harbor run; the profile uses the explicit `OPENAI_API_KEY` path so the
credential boundary is visible and reproducible.

The isolation profile is
`config/codex-isolation-fix-git-2.0.toml`. It keeps the same Codex package,
model, credential boundary, and one-attempt limit while selecting the small
public `fix-git` task. Its purpose is diagnosis, not leaderboard scoring: a
failure here points to the Codex/container path, while a pass points toward
task-specific workload or resource pressure in `gpt2-codegolf`.

The setup-smoke profile is
`config/codex-qemu-setup-smoke-2.0.toml`. It selects only `qemu-startup` to
check whether the Debian package-retry repair lets Codex start. This is
diagnostic evidence, not a replacement for the original matched cohort.

## Run the local AAH projection

The projection reads one JSON object per line and emits one JSON object per line.
It emits no prompts, task text, tool arguments, provider output, or trajectory
content:

```bash
printf '%s\n' '{"scenario_id":"synthetic-scenario-1","task_label":"smoke"}' | \
  uv run harbor-assurance aah-adapter
```

This first slice is a receipt/protocol projection, not a claim that AAH has
evaluated the coding agent's internal tool decisions. A local ATIF (Agent
Trajectory Interchange Format) scan checks the supported trajectory schema
versions, step/tool-call counts, and digest; it does not inspect or export
trajectory content. For the current Claude Code profile, a metadata-only scan
of the local JSONL event log is used when ATIF is missing; the receipt names
that source explicitly.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```

## Safety boundary

The adapter invokes the configured command with `shell=False`, a minimal child
environment, a separate process group, a wall-clock timeout, and bounded output
capture. A timeout, non-zero exit, or output cap produces a refused receipt; it
cannot produce a completed receipt. A clean process exit is not sufficient:
Harbor's structured result must also show that every trial completed with zero
errored trials. The benchmark score is recorded separately, so a completed
execution with reward `0.0` remains visibly benchmark-failed. The ATIF scan is a
second metadata check; `metadata-checked` is not a claim that the agent's
reasoning or tool choices were semantically safe.
