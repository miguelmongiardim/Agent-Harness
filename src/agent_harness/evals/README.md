# agent_harness.evals

## Purpose

`agent_harness.evals` owns deterministic local evaluations for Agent Harness.
It runs built-in eval specs and advanced eval routines, checks invariants over
the artifacts produced by normal harness execution, and writes eval scorecards.

The eval package validates harness behavior through public surfaces: task specs,
run summaries, context manifests, approvals, benchmark artifacts, provider audit
fixtures, exports, and release-oriented evidence. It should avoid private
runtime-object assertions when stored evidence can prove the behavior.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Eval spec, invariant, result, scorecard, and dataset schemas. |
| `runner.py` | Built-in eval definitions, eval execution, invariant checks, advanced eval routines, and JSON/Markdown report writing. |
| `adversarial.py` | Adversarial eval helpers for policy, approval, prompt-injection, and bypass scenarios. |
| `datasets.py` | Dataset and fixture helpers used by eval routines. |
| `metrics.py` | Metric helpers for eval and scorecard aggregation. |
| `scorecard.py` | Scorecard construction and interpretation helpers. |
| `__init__.py` | Lazily exports the public eval functions and built-in eval list. |

## Output

`write_eval_report()` writes timestamped JSON and Markdown reports under
`.agent-harness/evals/`. The JSON report uses `eval_scorecard.v1` and records
whether each eval passed, the invariant summary, and links to relevant artifacts
when the run produced them.

## Boundaries

Eval code may create temporary workspaces and drive the normal CLI/runtime
paths, but it should not create alternate execution behavior. If an eval needs a
new artifact, the underlying feature should write that artifact first, then the
eval should assert against it.
