# Agent Harness V0 Spike Audit

## Status

The current spike is frozen as reference material for the V0 recovery. Nothing
in the spike is accepted implementation until the relevant public behavior is
covered by a failing test, made green, and refactored while green.

## Repository State

- Git worktree: `true`
- Branch: `main`
- Tracked files before this recovery pass: `README.md`
- Existing spike state before this recovery pass: `README.md` modified,
  package code/docs/tests/project files untracked, `deep-research-report.md`
  ignored and private.
- Root `AGENTS.md` and `RTK.md` are not present in the repository; the active
  instructions came from the prompt.

## Validation Baseline

- `rtk python -m compileall -q src tests` passed.
- `.venv` contains only `pip`; `pytest` and `pydantic` are not installed there.
- `rtk .\.venv\bin\python.exe -m pytest` failed because `pytest` is missing.
- `rtk python -m pytest` failed because `pytest` is missing.
- CLI smoke checks with `PYTHONPATH=src` failed because `pydantic` is missing
  from the default interpreter.

This means the spike has a syntax baseline, but not a runnable test or CLI
baseline in the current environment.

## Classification

| Area | Classification | Reason | Required before reuse |
| --- | --- | --- | --- |
| `pyproject.toml` and package metadata | Salvage | PEP 621 metadata, src layout, package data, and script entrypoint are aligned with V0 direction. | Install-path test, `doctor` smoke, packaging check. |
| `src/agent_harness/schemas.py` | Salvage | Strict Pydantic boundary models match the PRD direction. It is monolithic but usable as a starting point. | Public schema tests for task, policy, tool, approval, context, eval, checkpoint, and summary. |
| `src/agent_harness/policy.py` and `policies/default.json` | Salvage with hardening | Ceiling narrowing, deny globs, path normalization, sensitivity, and redaction are present. | Behavior tests proving denied data cannot enter context or tools, task permissions cannot widen profile permissions, and redaction is model-facing. |
| `src/agent_harness/tools.py` | Salvage with fixes | Narrow tools and approval-bound patch logic exist. Runtime dry-run propagation and some bypass risks still need tests. | Tests for each public tool, patch non-mutation, stale approval rejection, allowed test commands, and denied paths. |
| `src/agent_harness/runtime.py` | Rewrite around salvageable pieces | It creates run artifacts and approvals, but dry-run is conflated with pending approval, resume does not complete run summary, and model/runtime boundaries are not yet proven. | Phase 0 dry-run test, Phase 4 approval test, Phase 6 resume test. |
| `src/agent_harness/storage.py` | Salvage with hardening | Run dirs, JSONL events, SQLite metadata, actions, approvals, and summaries exist. Event identity, append semantics, correlation ids, and fixed-seed reproducibility need work. | Stable artifact tests, event-summary consistency tests, duplicate run behavior test. |
| `src/agent_harness/retrieval.py` | Salvage with rewrite pressure | Fake and lexical retrievers exist, with optional Qdrant/FastEmbed boundary. Manifest reproducibility, denied retrieved content, and redaction need behavior coverage. | Reproducible manifest test, denied retrieval exclusion test, ingest determinism test. |
| `src/agent_harness/model.py` | Salvage with required change | The mock model uses tool observations and not task id alone, but it currently ignores manifest content in action selection. | Test that relevant context and observations change behavior. |
| `src/agent_harness/cli.py` | Salvage interface, likely rewrite internals | Most required commands exist. Behavior and output contracts are not validated in the current environment. | CLI integration tests for every V0 command before claims are kept. |
| `src/agent_harness/templates.py` | Rewrite mutation path | Template application evaluates a `patch_file` policy decision but writes directly and does not use approval-bound execution. | `template apply` behavior test proving policy mediation and expected write behavior. |
| `src/agent_harness/evals.py` | Rewrite around public eval behavior | A single built-in eval exists, but V0 requires success, denial, injection, approval, and replay scenarios with scorecards. | First adversarial eval test that hard-fails on policy bypass. |
| `src/agent_harness/exporters.py` | Salvage | SARIF export from policy decisions is a plausible starting point. | Export tests proving SARIF, JSON, and Markdown reflect run evidence. |
| Existing tests in `tests/` | Salvage as characterization | They cover useful slices but are too shallow for V0 acceptance and currently cannot run without dev dependencies. | Reorganize into public behavior unit/integration/e2e/adversarial tests as slices require. |
| `README.md` and current public docs | Rewrite for accuracy | They describe V0 as already demonstrated, while the current environment cannot run the CLI/tests and some behavior is only partial. | Docs scanner or review gate that blocks unsupported claims. |
| `docs/research-foundations.md`, `docs/security-model.md`, `docs/context-packs.md`, `docs/evaluations.md`, `docs/roadmap.md` | Salvage with edits | The boundaries mostly match the accepted V0 plan, but claims must track implemented behavior. | Update incrementally after each green slice. |
| Examples, fixtures, and `python-lib` template | Salvage | They provide useful local behavior targets. | Fixture and template tests through CLI workflows. |
| `.venv`, `__pycache__`, live artifacts | Discard | Generated environment/cache state is not source. | Keep ignored; recreate from documented setup. |
| `deep-research-report.md` | Salvage privately | It controls target structure and research background but remains private/untracked. | Clean only stable, non-private conclusions into public docs when needed. |

## Immediate Recovery Sequence

1. Treat this audit plus the PRD and plan as the Phase -1 gate.
2. Do not migrate or restructure code until the Phase 0 first RED test exists.
3. Start Phase 0 with the CLI dry-run artifact test.
4. Pull spike code forward only when it makes that public behavior pass.
5. Rewrite docs alongside behavior so public claims stay true.
