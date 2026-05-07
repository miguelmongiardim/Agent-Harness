# agent_harness

## Purpose

`agent_harness` is the installed Python package for the local Agent Harness CLI.
It coordinates deterministic agent runs, policy enforcement, retrieval,
templates, skills, governance evidence, exports, and release checks while
keeping each durable behavior inside an explicit package boundary.

The top-level package should stay thin. Command routing, compatibility shims,
cross-cutting helpers, and source data live here, but domain behavior should be
placed in the package that owns it. For example, template rendering belongs in
`templates`, provider envelopes belong in `model`, and approval-bound tool
execution belongs in `tools`.

## Top-Level Modules

| Module | Role |
| --- | --- |
| `cli.py` | Builds the `agent-harness` argparse surface and delegates commands to the owning packages. |
| `__main__.py` | Enables `python -m agent_harness` by calling the CLI entry point. |
| `defaults.py` | Stores default local policy/configuration snippets used when initializing workspaces. |
| `doctor.py` | Performs lightweight project health checks for expected config, policy, task, and docs locations. |
| `docs_check.py` | Scans user-facing project documentation for unsupported capability claims, missing sections, broken local links, schema reference issues, and Markdown hygiene problems. |
| `demos.py` | Builds deterministic local demo evidence, including the provider-audit demo and the Python refactor demo markers used by release checks. |
| `migration.py` | Reports and optionally writes safe public schema migrations for config, task, and policy artifacts. |
| `provider_input.py` | Builds provider-input manifests after policy redaction and approval decisions have been applied. |
| `release.py` | Collects local release-readiness evidence across docs, package metadata, demos, schemas, optional adapters, governance, and evidence pack checks. |
| `retrieval_indexes.py` | Owns persisted retrieval index lifecycle helpers used by retrieval CLI commands. |
| `retrieval_scorecards.py` | Builds local retrieval-quality scorecards from configured retrieval examples and evidence. |
| `schema_base.py` | Provides strict Pydantic model defaults shared by public schemas. |
| `utils.py` | Contains small deterministic helpers for JSON IO, hashing, time, IDs, and path normalization. |

## Package Boundaries

| Package | Owns |
| --- | --- |
| `benchmarks` | Local benchmark packs, adapter staging, per-case runs, baseline/orchestration comparison, and comparison interpretation. |
| `bundled_benchmarks` | Packaged benchmark case data consumed by `benchmarks`. |
| `bundled_skills` | Packaged Markdown skill guidance consumed by `skills`. |
| `bundled_templates` | Packaged template manifests, registry data, and scaffold files consumed by `templates`. |
| `config` | Config loading, minimal YAML parsing, schema normalization, and model serialization helpers. |
| `context` | Document ingestion, chunking, retrieval, context manifests, and retrieval provenance. |
| `core` | Deterministic model compatibility exports and the native runtime implementation. |
| `evals` | Built-in local evaluations and scorecard artifacts. |
| `evidence` | Review-only evidence pack construction, prerequisite checks, indexes, findings, and control mappings. |
| `exporters` | Run-summary export formats: JSON, Markdown, and SARIF. |
| `governance` | Workspace governance summaries, checks, reports, and exports. |
| `mcp` | Read-only MCP resources, prompts, envelopes, access logs, and optional stdio serving. |
| `model` | Model-client contracts, deterministic mock behavior, provider profiles, provider schemas, and provider adapters. |
| `operator` | Loopback local operator API and packaged static UI for existing run and evidence artifacts. |
| `orchestration` | Multi-child orchestration specs, policy gates, stores, run/resume flows, and aggregate exports. |
| `policy` | Policy profiles, path mediation, sensitivity decisions, redaction, provider-use approvals, and tool approval decisions. |
| `provider_fixtures` | Recorded provider response fixtures used by provider tests and demos. |
| `runtimes` | Runtime adapter selection shims and optional adapter proofs around the native runtime. |
| `security` | Task security scanning and advisory report collection. |
| `skills` | Skill discovery, validation, rendering, task resolution, and run skill manifests. |
| `storage` | Append-only run directories, JSONL events, approvals, summaries, workspace metadata, and SQLite indexes. |
| `tasks` | Public task schema contract. |
| `telemetry` | Deterministic event payload, logger-name, and trace-id helpers. |
| `templates` | Template registry, local/bundled pack loading, validation, rendering, apply planning, and apply evidence. |
| `tools` | Typed tool arguments, policy-mediated execution, patch diffs, test command execution, git status, and approval-bound git commits. |

## Development Guidance

Before adding a new module, identify the public contract it affects. CLI output,
schema versions, run artifacts, approval records, provider manifests, template
manifests, and evidence exports are public behavior and need focused tests.

Keep dependency direction intentional:

- The CLI may call domain packages, but domain packages should not depend on
  CLI command code.
- Policy remains the shared gate for paths, provider input, tool execution,
  template writes, generated context, skill context, and orchestration authority.
- Runtime code coordinates domain packages but should not absorb package-specific
  parsing, rendering, validation, export, or storage rules.
- Optional integrations should lazy-load their dependencies and fail clearly when
  the extra is unavailable.
