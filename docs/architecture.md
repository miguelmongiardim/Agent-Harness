# Architecture

Agent Harness keeps the CLI and artifact contracts stable while organizing the
runtime around explicit ownership boundaries.

## Package Boundaries

- `agent_harness.core` owns deterministic model behavior and run orchestration.
- `agent_harness.policy` owns policy loading, path mediation, sensitivity
  classification, redaction, and provider-use decisions.
- `agent_harness.context` owns document ingestion, retrieval, context manifest
  assembly, and retrieval provenance.
- `agent_harness.tools` owns typed tool arguments, policy-mediated tool
  execution, and the exact-state `git_commit` planning/execution boundary.
- `agent_harness.benchmarks` owns packaged local benchmark sample packs,
  workspace staging, result mapping, and evidence-backed benchmark exports.
- `agent_harness.templates` owns bundled template catalog behavior today and is
  the V7 boundary for local pack source discovery, manifest loading,
  validation, deterministic rendering, planning, application evidence, and
  policy-mediated template writes.
- `agent_harness.release` owns local release-readiness evidence collection.
- `agent_harness.model`, `agent_harness.runtimes`, `agent_harness.storage`,
  `agent_harness.telemetry`, `agent_harness.evals`, and
  `agent_harness.exporters` provide the report's package-level structural
  boundaries.

## Deep Research Layout Reconciliation

`deep-research-report.md` describes the target source layout. The current
implementation now materializes that `src/agent_harness` tree for the named
packages and leaf modules. Legacy top-level compatibility shims have been
removed; callers should import from the report-shaped package paths directly.

Current public paths:

- Public inputs: `config.v2`, `task.v2`, `policy.v2`, and `template.v2`.
- Runtime orchestration: `agent_harness.runtimes.native` and
  `agent_harness.core.runtime`.
- Optional LangGraph boundary proof: `agent_harness.runtimes.langgraph_adapter`.
- Context ingestion and retrieval: `agent_harness.context.retrieval`,
  `agent_harness.context.builder`, and `agent_harness.context.chunking`.
- Provider adapters: `agent_harness.model.adapters`.

Some report leaf modules are explicit adapter boundaries rather than completed
features. For example, `agent_harness.runtimes.mcp_adapter` and the live
OpenAI-compatible adapter entry point fail clearly with `UnsupportedAdapterError`
until those phases are implemented.

V6 adds an `agent_harness.operator` boundary for the local operator surface.
The current implementation has the app factory, `/health`, token-gated run
list/detail APIs for existing run artifacts, context manifest inspection, policy
inspection, and artifact-status reporting for denied, missing, and malformed
run evidence. It also exposes approval listing and approve/deny decisions that
delegate to the existing approval service, and the packaged static UI now uses
that same local decision API for browser approval controls. The completed
boundary should sit
above storage, policy, approvals, exports, provider evidence, and run artifacts.
It exposes existing evidence through a local API and packaged static UI without
becoming a runtime, policy engine, approval engine, or arbitrary file server.

## Dependency Direction

The CLI depends on the runtime, policy, context, tool, storage, template, eval,
and export boundaries. Core runtime orchestration coordinates these boundaries
but should not absorb their detailed implementation. Policy remains the common
gate for context inclusion, provider input, template writes, tool execution, and
separate git commit approval.

Benchmark adapters are deliberately thin. They prepare local sample workspaces,
map SWE-bench-style or terminal-task adapter evidence, and then call the native
runtime, approval path, and JSON exporter; benchmark results are pointers to
real run evidence rather than independent synthetic reports.

Provider transports live under `agent_harness.model.adapters` behind
`ProviderGateway`; they call the deterministic model contract or recorded
fixtures without becoming the runtime itself. Storage remains the append-only
evidence boundary for run artifacts, approvals, checkpoints, and event logs.

Template loading is a schema and catalog boundary. `template.v2` manifests carry
compatibility, capability, generated-schema, provider, policy, retrieval, and
demo metadata. Template application remains approval-bound and records applied
template id and version in workspace metadata.

The V7 template-pack plan keeps local pack behavior inside
`agent_harness.templates`: `template.v2.toml` loading, configured local
directory discovery, validation diagnostics, deterministic substitution,
dry-run and preview planning, clean apply evidence, and
`template_application.v1` construction. Runtime and policy code should
coordinate approvals and write permissions without absorbing pack parsing or
rendering rules.

Schema migration stays outside runtime execution. The migration module reports
original and proposed effective schema versions by default, and `--write` only
performs deterministic safe upgrades.

The LangGraph adapter is deliberately narrow. It lazy-loads the optional
`langgraph` package, delegates the covered execution path through the native
runtime, and records `runtime_adapter.json` plus a `runtime_adapter_selected`
event. It proves the framework boundary can share policy and audit artifacts
without making LangGraph the primary runtime.

## Compatibility And Roadmap Boundaries

The v1.0.0 compatibility and deprecation policy is defined in
[the V3 PRD](prd-agent-harness-v3.md). Until later phases implement and test
them, enterprise readiness, compliance readiness, MCP support, multi-agent
orchestration, production Qdrant server mode, external catalogs, hosted web/API
platform behavior, and cloud deployment remain roadmap scope. V6 narrows the
near-term platform direction to loopback-only local operator inspection and
approval over existing artifacts.
