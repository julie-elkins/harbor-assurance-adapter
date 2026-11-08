# Harbor Assurance Adapter

## Purpose

This repository provides a small execution boundary around Harbor, the benchmark
runner, and a metadata-only projection into the Agent Assurance Harness (AAH), the
secondary assurance check.

The benchmark score answers: “Did the coding task pass?”

The AAH projection answers: “Did the run produce the required observable metadata
without exposing raw content or claiming success after a refusal?”

These are separate questions. Combining them would allow a high task score to hide
an unsafe or unverifiable run.

## Dependency graph

```text
pinned TOML
    |
    v
preflight budget validation
    |
    v
bounded Harbor subprocess
    |
    +--> local-only stdout/stderr and trajectories
    |
    v
metadata-only receipt
    |
    +--> local ATIF structure scan (digest and bounded counts only)
    |
    v
AAH JSONL projection

evaluation manifest + receipt aggregator
```

The Harbor process is the upstream dependency. A failed, timed-out, or output-capped
process cannot produce a completed receipt. The AAH projection is a lateral check:
it can report a refusal without hiding the Harbor failure.

## Data boundary

The receipt contains identifiers, versions, counts, statuses, digests, timing, and
declared cost observations. It does not contain prompts, tool arguments, provider
responses, task text, or raw trajectory content. Execution status and benchmark
status are separate fields: a clean Harbor process can still have a failed
benchmark score. The ATIF scan reports structural metadata only; it does not
evaluate agent reasoning or tool decisions.

Raw process output and trajectories are local-only and ignored by Git. The current
preflight cost check is a declared estimate, not a provider billing guarantee.

The public evaluation manifest defines the matched cohort and metric formulas.
The receipt aggregator consumes only validated receipt fields. Pilot receipts
and matched-cohort receipts must remain distinguishable; mechanically combining
them would produce a number with an unclear denominator.

## Runner profiles

The first runner is mini-swe-agent because its linear trajectory is straightforward
to inspect. The second profile uses Harbor's built-in Claude Code agent, and the
third profile uses Harbor's built-in Codex agent with a published npm version pin.
Both reuse the same receipt and ATIF contracts. The Codex compatibility fix
corrects Harbor's package-version boundary without changing Harbor's execution
path. The receipt also records bounded agent-event metadata so an abrupt runner
exit is distinguishable from a benchmark failure.
