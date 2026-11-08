# Build specification

## Building

A public-data-only Harbor execution adapter that runs bounded benchmark
invocations for comparable runners, stores raw output locally, writes
metadata-only receipts, exposes an AAH-compatible JSONL projection, and produces
a reproducible public evaluation record.

## Not building

- A fork or patch of Harbor, Terminal-Bench, mini-swe-agent, Claude Code, or Codex.
- A claim that the assurance harness itself is a leaderboard score.
- An automatic external publication or leaderboard comment.
- A hosted dashboard or model router.
- A raw-trajectory upload path.
- A provider billing guarantee.
- A path for private certification content.

## Done when

- A pinned configuration validates before execution.
- A declared pilot estimate above the ceiling is refused.
- The subprocess uses `shell=False`, a minimal environment, a process-group timeout,
  and an output cap.
- A successful process produces a metadata-only receipt.
- A completed receipt requires a Harbor result with all trials completed and zero
  errored trials, not merely a zero process exit code.
- The receipt distinguishes clean execution from benchmark pass/fail/partial
  status.
- A completed run scans the local ATIF trajectory for schema shape, bounded
  step/tool-call counts, and a digest without exporting trajectory content.
  The scanner explicitly supports the ATIF versions emitted by the validated
  mini-swe-agent, Claude Code, and Codex Harbor paths.
- The Claude Code profile pins the runner release, model budget, and Harbor
  agent name without requiring a second custom container shim.
- The Codex profile pins a published npm package version, passes only
  `OPENAI_API_KEY`, and uses Harbor's built-in agent path.
- A refused agent run records the Harbor exception class, coarse failure phase,
  and bounded local event summary without exporting agent content.
- A Codex isolation profile can select one pinned public task without changing
  the runner, model, credential boundary, or receipt contract.
- A timeout, non-zero exit, or output cap produces a refused receipt.
- The AAH projection emits only identifier-level fields and structured refusals.
- Tests cover budget refusal, receipt redaction, process failure classification,
  and AAH projection.
- The public evaluation manifest pins the benchmark revision, task-set revision,
  agent profiles, and publication boundary.
- The metric contract reports execution completion separately from benchmark
  correctness and assurance evidence.
- Aggregate metrics can be computed from metadata-only receipts without reading
  raw trajectories or provider output.

## Pilot stop condition

The first live pilot is one public task, one attempt, and a $25 declared ceiling.
The broader $100 pilot remains a later cap: $25 smoke validation followed by up to
$75 only after the smoke receipt and AAH projection are reviewed.
