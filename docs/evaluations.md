# Evaluations

The eval suite is designed to catch workflow regressions rather than benchmark model
quality.

The bundled eval suite focuses on:

- success scenarios over the bundled Python refactor task
- denied-context and policy-bypass adversarial checks
- prompt-injection resistance over retrieved local docs
- approval pause/resume lifecycle completion
- fixed-seed replay stability for run artifacts
- local benchmark-shaped sample packs for SWE-bench-style and terminal-task
  workflows

Each `agent-harness eval` run writes a JSON and Markdown scorecard under
`.agent-harness/evals/`. Scorecards record pass/fail status per scenario plus
artifact links so failures can be inspected from stored run evidence.

Benchmark sample packs are not claims of benchmark comparability. They are
small packaged cases that import into local workspaces, run through the same
task, policy, approval, runtime, and export paths as normal Agent Harness runs,
and produce `benchmark_result.v1` artifacts that point back to run exports.

The mock model must consume real task specs, context manifest content, and tool
observations. Tests intentionally verify that changing observations changes
proposed behavior and that task ids alone are insufficient to drive actions.
