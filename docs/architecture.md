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
- `agent_harness.model`, `agent_harness.runtimes`, `agent_harness.templates`,
  `agent_harness.storage`, `agent_harness.telemetry`, `agent_harness.evals`,
  and `agent_harness.exporters` provide the report's package-level structural
  boundaries.

## Deep Research Layout Reconciliation

`deep-research-report.md` describes the target source layout. The current
implementation now materializes that `src/agent_harness` tree for the named
packages and leaf modules. Legacy top-level compatibility shims have been
removed; callers should import from the report-shaped package paths directly.

Current public paths:

- Runtime orchestration: `agent_harness.runtimes.native` and
  `agent_harness.core.runtime`.
- Context ingestion and retrieval: `agent_harness.context.retrieval`,
  `agent_harness.context.builder`, and `agent_harness.context.chunking`.
- Provider adapters: `agent_harness.model.adapters`.

Some report leaf modules are explicit adapter boundaries rather than completed
features. For example, `agent_harness.runtimes.langgraph_adapter`,
`agent_harness.runtimes.mcp_adapter`, and the live OpenAI-compatible adapter
entry point fail clearly with `UnsupportedAdapterError` until those phases are
implemented.

## Dependency Direction

The CLI depends on the runtime, policy, context, tool, storage, template, eval,
and export boundaries. Core runtime orchestration coordinates these boundaries
but should not absorb their detailed implementation. Policy remains the common
gate for context inclusion, provider input, template writes, tool execution, and
separate git commit approval.

Provider transports live under `agent_harness.model.adapters` behind
`ProviderGateway`; they call the deterministic model contract or recorded
fixtures without becoming the runtime itself. Storage remains the append-only
evidence boundary for run artifacts, approvals, checkpoints, and event logs.
