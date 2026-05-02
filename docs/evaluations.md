# Evaluations

The eval suite is designed to catch workflow regressions rather than benchmark model
quality.

The bundled eval suite focuses on:

- success scenarios over the bundled Python refactor task
- the provider-audit demo golden path with provider-input, provider-use
  approval, and provider-call evidence
- provider-core deterministic boundaries covering mock provider execution,
  recorded OpenAI-compatible fixtures, redacted provider evidence artifacts,
  malformed provider output rejection, unauthorized provider tool denial,
  hard-denied provider-input exclusion, provider approval drift blocking, and
  optional live-smoke skip behavior when opt-in is absent
- denied-context and policy-bypass adversarial checks
- prompt-injection resistance over retrieved local docs
- approval pause/resume lifecycle completion
- fixed-seed replay stability for run artifacts
- local benchmark-shaped sample packs for SWE-bench-style and terminal-task
  workflows
- benchmark adapter evidence for task import, workspace preparation, policy
  selection, run execution, eval result mapping, export paths, and retrieval
  backend evidence when present
- pack-level benchmark comparison evidence that verifies each compared local
  sample has an inspectable single-agent baseline before orchestration modes
- a local dense-retrieval benchmark scenario that uses deterministic fixture
  behavior rather than public dataset downloads
- optional LangGraph boundary compatibility through the same native policy and
  audit evidence path
- optional `eval.v1` `expected_skills` assertions that verify included skill
  ids from recorded `skill_manifest.v1` run evidence

Each `agent-harness eval` run writes a JSON and Markdown scorecard under
`.agent-harness/evals/`. Scorecards record pass/fail status per scenario plus
artifact links so failures can be inspected from stored run evidence.

Benchmark sample packs are not claims of benchmark comparability. They are
small packaged cases that import into local workspaces, run through the same
task, policy, approval, runtime, and export paths as normal Agent Harness runs,
and produce `benchmark_result.v1` artifacts that point back to run exports.
The bundled adapters prove local import/run/export behavior only; they are not
full SWE-bench or Terminal-Bench executions.

Benchmark comparison evals are local evidence checks. They run the bundled
sample pack through `benchmark_comparison_suite.v1`, verify that every per-case
comparison links an inspectable single-agent baseline, and preserve skipped
mode evidence. They do not claim external benchmark comparability or promote
role defaults.

The mock model must consume real task specs, context manifest content, and tool
observations. Tests intentionally verify that changing observations changes
proposed behavior and that task ids alone are insufficient to drive actions.

## Provider Core Evals

The `provider-core-deterministic-boundaries` eval is the normal CI proof for
v1.1.0 provider core. It uses mock and recorded-fixture provider paths only, so it
does not require provider credentials or outbound network access.

The eval writes inspectable run artifacts for provider input, provider calls,
redacted prompts, redacted responses, approval decisions, and failure events.
It verifies that provider output is validated as `provider_action_envelope.v1`
before runtime action planning and that policy remains the permission ceiling
for proposed tools.

Optional live OpenAI-compatible smoke remains outside normal eval execution.
It is skipped unless `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1` and the required
endpoint/API-key environment variables are present.
