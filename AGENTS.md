# AGENTS.md

## Purpose

This repository is a Python CLI for controlled, policy-gated agent workflow
experiments. Keep future agent work grounded in implemented behavior, explicit
public contracts, and reproducible local evidence.

Follow the user-level Codex contract for global workflow, git safety, and
session-memory rules. This file only captures repo-local expectations.

## Repository Boundaries

- `agent_harness.core` owns deterministic model behavior and run orchestration.
- `agent_harness.policy` owns permission ceilings, path mediation,
  classification, redaction, and provider-use decisions.
- `agent_harness.context` owns ingestion, retrieval, context manifests, and
  retrieval provenance.
- `agent_harness.tools` owns typed tool execution and approval-bound mutation
  planning, including the separate `git_commit` boundary.
- `agent_harness.templates` owns bundled template registry, validation, and
  approval-bound template application.
- `agent_harness.storage` owns append-only run evidence, approvals,
  checkpoints, summaries, and workspace metadata.
- `agent_harness.model` and `agent_harness.runtimes` are provider/runtime
  adapter boundaries. Optional adapters must fail clearly when unavailable.
- `agent_harness.evals`, `agent_harness.exporters`, and `agent_harness.release`
  own scorecards, exports, and release-readiness evidence.

Do not collapse detailed implementation into `core.runtime` when an existing
boundary owns it. Keep policy as the shared gate for context inclusion, provider
input, tools, templates, and commits.

## Public Contracts

Treat these as public behavior unless a plan explicitly changes them:

- CLI commands and JSON/Markdown/SARIF output shapes.
- Schema versions and compatibility paths for config, task, policy, template,
  context manifest, retrieval, approval, provider, benchmark, and release
  artifacts.
- Run directories, append-only JSONL events, approval records, checkpoints,
  summaries, exports, and release evidence.
- Bundled templates, registry metadata, generated schema versions, and
  approval-bound template apply behavior.
- Provider-input evidence, redaction behavior, trust-zone policy, and explicit
  provider-use approval binding.

Behavioral changes to these surfaces need focused tests. Schema, CLI, artifact,
or compatibility changes need integration coverage.

## Development Commands

Use the smallest relevant check first, then broaden when the change touches a
public surface.

```powershell
uv run agent-harness doctor
uv run pytest
uv run python -m pre_commit run --all-files
uv run agent-harness eval
uv run agent-harness release readiness
```

Useful narrower checks include:

```powershell
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/adversarial
uv run pytest tests/e2e
uv run agent-harness docs check
uv run agent-harness template validate --all
```

If `uv` is installed but unavailable on the inherited process `PATH`, first try
the user-local executable relative to this repository root:

```powershell
& ..\.local\bin\uv.exe run agent-harness docs check
```

This is a session-environment fallback, not a reason to change project commands
or install a second copy of `uv`.

Optional live-provider or retrieval-extra paths must remain opt-in and must not
be required for the default local suite.

## Documentation And Plans

- Keep docs aligned with implemented behavior. Do not claim enterprise,
  compliance, hosted, remote-embedding, production-Qdrant, MCP, multi-agent, or
  web/API support until tests and docs prove it.
- PRDs and phase plans belong in `docs/` and `plans/`. They may describe future
  work, but README and capability docs should clearly separate current behavior
  from roadmap scope.
- Do not use durable repo docs as a session worklog. Volatile working context
  belongs in the user's Codex Workspace.
- Update docs with behavior changes when the public claim would otherwise become
  stale or misleading.

## Artifacts And Generated State

- `.agent-harness/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, virtual
  environments, build outputs, and release/demo evidence are generated state
  unless a task explicitly asks to inspect or refresh them.
- Do not commit secrets, live provider payloads, raw provider requests or
  responses, private datasets, or machine-local cache paths.
- Release evidence should be regenerated through the CLI commands that own it,
  not hand-edited.

## Testing Expectations

- Add or update tests for behavior changes, especially policy gates, redaction,
  approval binding, retrieval provenance, template writes, exports, and release
  readiness.
- Prefer behavior-oriented tests over implementation-shape tests.
- Preserve deterministic local execution. Network, external services, live
  provider calls, and optional dependency paths must be gated by explicit opt-in.
- Run `agent-harness docs check` when changing public docs, roadmap boundaries,
  or capability claims.
