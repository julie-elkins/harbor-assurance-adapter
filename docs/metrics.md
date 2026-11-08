# Evaluation metrics

The study reports execution and task correctness separately. This prevents a
runner that finished without errors from being mistaken for a runner that
solved the task, and prevents a provider or setup failure from being counted as
a benchmark failure.

For each attempted task:

- A **clean execution** is a receipt with `status = "completed"`, a clean Harbor
  result, zero errored trials, no timeout, no output cap, and a zero process
  exit code.
- A **benchmark pass** is a receipt with `benchmark_status = "passed"`.
- A **benchmark observation** is a clean execution whose benchmark status is
  `passed`, `failed`, or `partial`.
- An **invalid benchmark result** is a run whose agent completed but whose
  verifier environment failed before producing a trustworthy task result.
  It is reported separately and is not evidence about agent correctness.
- **Assurance evidence** is a receipt with `atif_scan_status = "passed"` and
  `agent_trace_status = "metadata-checked"`. This means the adapter checked
  bounded metadata; it is not a claim that the agent's reasoning was safe.

For an agent with `N` attempted tasks:

| Metric | Formula | Interpretation |
| --- | --- | --- |
| Execution completion rate | clean executions / `N` | Did the run finish as a valid Harbor execution? |
| Benchmark pass rate | benchmark passes / `N` | How many attempted tasks passed verification? |
| Conditional benchmark pass rate | benchmark passes / clean executions | How often did a clean execution solve the task? |
| Benchmark observation rate | benchmark observations / clean executions | How often did a clean run produce a usable verifier result? |
| Invalid benchmark runs | verifier-environment failures / `N` | How often did the evaluation environment prevent a valid score? |
| Assurance evidence rate | assurance-checked runs / `N` | How often did the receipt contain the expected metadata checks? |
| Observed cost | sum of receipt costs | What Harbor reported, not a billing guarantee. |

The denominators are intentionally visible. Provider, setup, timeout, and
incomplete-agent failures remain execution outcomes and are not silently
converted into benchmark failures. A clean execution with no verifier result
does not count as a benchmark pass, is reported as invalid when the verifier
environment is known to be broken, and reduces the observation rate.
