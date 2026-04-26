# Evaluations

The eval suite is designed to catch workflow regressions rather than benchmark model
quality.

The bundled eval suite focuses on:

- success scenarios over the bundled Python refactor task
- denied-context and policy-bypass adversarial checks
- prompt-injection resistance over retrieved local docs
- approval pause/resume lifecycle completion
- fixed-seed replay stability for run artifacts

Each `agent-harness eval` run writes a JSON and Markdown scorecard under
`.agent-harness/evals/`. Scorecards record pass/fail status per scenario plus
artifact links so failures can be inspected from stored run evidence.

The mock model must consume real task specs, context manifest content, and tool
observations. Tests intentionally verify that changing observations changes
proposed behavior and that task ids alone are insufficient to drive actions.
