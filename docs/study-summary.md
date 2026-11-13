# Public study summary

This study evaluates two different questions about coding agents:

1. Did the benchmark task finish with a usable, verifiable result?
2. Did the run leave bounded metadata that the Agent Assurance Harness (AAH),
   the secondary assurance check, can inspect without publishing sensitive
   execution content?

The benchmark score answers the first question. AAH metadata answers the
second. Neither result is a claim that the agent's reasoning or tool choices
were semantically safe.

## Matched comparison results

A **matched cohort** means the agents used the same ten public
Terminal-Bench 2.0 tasks, one attempt per task, the same task-set revision, and
the same Finch compatibility path. The denominators remain visible because a
provider, setup, or timeout failure is an execution outcome, not automatically
a benchmark failure.

| Runner | Attempted | Clean executions | Benchmark observations | Passes | Execution completion | Pass rate / attempted | Conditional pass rate | Observed cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex (`openai/gpt-5.5`) | 10 | 10 | 10 | 7 | 100% | 70% | 70% | $10.098631 |
| mini-swe-agent (`anthropic/claude-opus-4-6`) | 10 | 9 | 9 | 6 | 90% | 60% | 66.7% | $16.182813 |

The Codex report is
[codex-comparison-10-v3.json](results/codex-comparison-10-v3.json). The
mini-swe-agent report is
[mini-swe-agent-comparison-10-v3.json](results/mini-swe-agent-comparison-10-v3.json).

The mini-swe-agent cohort's tenth task, `qemu-startup`, failed during agent
setup and did not produce a trustworthy benchmark observation. It is therefore
included in execution reliability and excluded from the conditional benchmark
denominator. The overall attempted-task pass rate remains visible as 6/10.

### Post-bridge mini-swe-agent follow-up

After the credential transport and evidence-path changes merged, we ran the
same ten-task revision again as a new follow-up cohort. It is not combined with
the original denominator:

| Runner | Attempted | Clean executions | Benchmark observations | Passes | Execution completion | Pass rate / attempted | Conditional pass rate | Observed cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mini-swe-agent (`anthropic/claude-opus-4-6`) | 10 | 10 | 10 | 9 | 100% | 90% | 90% | $16.530741 |

The follow-up improved the observed execution completion rate from 90% to
100% and the attempted-task pass rate from 60% to 90%. This is a follow-up
observation, not causal proof that the evidence bridge caused the improvement:
the run also reflects a new provider execution and recovered environment
conditions. The remaining `raman-fitting` failure was a clean
task-correctness failure, not an execution failure.

The public-safe report is
[mini-swe-agent-comparison-10-post-bridge-v1.json](results/mini-swe-agent-comparison-10-post-bridge-v1.json).

### Replication attempt: non-clean diagnostic

We then attempted one replication of the post-bridge cohort with the same ten
tasks and configuration. The run reached terminal states for all ten tasks,
but `qemu-startup` timed out during agent execution, so this is not a clean
replication and is not added to a leaderboard denominator:

| Runner | Attempted | Clean executions | Benchmark observations | Passes | Execution completion | Pass rate / attempted | Conditional pass rate | Observed cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mini-swe-agent replication | 10 | 9 | 9 | 7 | 90% | 70% | 77.8% | $18.547999 |

The two observed benchmark failures were `gpt2-codegolf` and
`raman-fitting`, both clean task-correctness failures. `qemu-startup` is
reported as an execution error with no benchmark observation. The result does
not establish that the post-bridge 90% observation reproduced, and it does not
prove that the bridge caused or failed to cause any change.

The public-safe diagnostic report is
[mini-swe-agent-replication-10-v1.json](results/mini-swe-agent-replication-10-v1.json).

The checked-in
[cohort comparison report](results/cohort-comparison-v1.json) is a no-cost,
offline reproducibility check across the original mini-swe-agent cohort, Codex,
and the post-bridge mini-swe-agent cohort. It recomputes the metrics from the
public task records and checks the benchmark revision, task-set revision,
model/configuration, task count, and attempts before emitting task-level
deltas. It does not add the follow-up to the original denominator or make a
causal claim about the bridge.

Claude Code was exercised during the study, but its provider-quota and evidence
path interruptions prevented a fully comparable public ten-task result from
being included here. Its runs remain documented in the
[study log](study-log.md). We do not infer a leaderboard accuracy score from
those partial or diagnostic runs.

## Diagnostic findings

These results answer specific troubleshooting questions. They are not additions
to the matched-cohort denominators.

### Raman unit-contract ablation

The original `raman-fitting` task failed after a clean execution because the
agent used the native wavelength axis while the verifier expected calibrated
Raman-shift units. A **unit contract** is the explicit statement of which
coordinate system and units the output must use.

We then ran one controlled ablation (a small experiment that changes one
condition) with the conversion instruction delivered directly into the
mini-swe-agent prompt:

- clean execution: 1/1
- benchmark observations: 1/1
- benchmark passes: 1/1
- observed cost: $0.198360

The result supports a task-specific interpretation-sensitivity finding: the
explicit unit contract changed the outcome. It does not prove that all
under-specified tasks behave this way, and it is not a leaderboard score.

See [mini-swe-agent-raman-unit-contract-ablation-v3.json](results/mini-swe-agent-raman-unit-contract-ablation-v3.json)
and the versioned
[extra instruction](../diagnostics/raman-unit-contract/extra-instruction.md).

### Post-hardening execution diagnostic

The later mini-swe-agent diagnostic reached all ten terminal states, with
8/10 clean executions and two errors. Because the run was not clean, it has no
aggregate benchmark score. Its failure breakdown included agent timeouts and a
provider-quota signal. This is execution-reliability evidence, not an 8/10
accuracy result.

See [mini-swe-agent-comparison-10-v4.json](results/mini-swe-agent-comparison-10-v4.json).

## Assurance finding

The study found that benchmark success does not automatically guarantee that
the expected trajectory artifact exists. In one controlled Claude Code smoke
run, a complete local JSONL event log existed while Harbor did not produce an
ATIF (Agent Trajectory Interchange Format) trajectory file. The adapter refused
to label the run ATIF-verified and recorded the fallback evidence source
explicitly.

This is the central assurance result: benchmark correctness and evidence
completeness are separate properties. A run can pass the task while still
failing the evidence contract needed to support a reproducible public claim.

## What this study does not claim

- It does not claim that Codex or mini-swe-agent is universally better.
- It does not present the Raman ablation as a matched benchmark result.
- It does not convert provider, setup, timeout, or transport failures into
  benchmark failures.
- It does not publish raw trajectories, prompts, tool arguments, provider
  responses, credentials, or private content.
- It does not treat an AAH metadata check as a safety evaluation of the
  agent's internal reasoning.
- It does not treat observed Harbor cost as a provider billing guarantee.

The reproducibility contract, metric formulas, and decision history are in the
[evaluation manifest](evaluation-manifest.toml),
[metrics documentation](metrics.md), and
[study log](study-log.md).
