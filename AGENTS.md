# AGENTS.md

## Purpose

This repository runs public benchmark tasks through Harbor and projects only
identifier-level execution metadata into the Agent Assurance Harness (AAH). AAH is
the second assurance check; it is not the benchmark grader.

## Boundaries

- Public synthetic or benchmark data only. Never add private exam content, prompts,
  tool arguments, provider responses, credentials, or raw trajectories to Git.
- Real trajectories and process logs are local-only under `runs/`, which is ignored.
- The receipt is metadata-only: versions, identifiers, counts, statuses, digests,
  timing, and bounded cost observations.
- The adapter must use argument vectors with `shell=False`, a minimal child
  environment, a process-group timeout, and an output cap.
- A preflight estimate is not a provider billing guarantee. Never describe it as one.
- An incomplete or refused run is not a passing run.

## Workflow

The dependency graph is:

1. Load and validate the pinned run configuration.
2. Check the task/attempt cost estimate against the declared pilot ceiling.
3. Run one Harbor command with bounded local capture.
4. Write a metadata-only receipt.
5. Optionally project the receipt into the AAH JSONL adapter protocol.

Steps 3–4 are sequential. Step 5 may be run only after a receipt exists. A Harbor
failure stops the success path; the AAH projection reports a refusal rather than
inventing a clean result.

## Verification

Run the standard-library test suite before a commit:

```bash
python -m unittest discover -s tests -v
```

For a real run, use a small public smoke test first and state the cost ceiling,
task count, attempt count, timeout, and stop condition in the configuration.

## Staging

Stage one path per `git add` command. Never use `git add .`, `git add -A`, or
`git commit -a`.
