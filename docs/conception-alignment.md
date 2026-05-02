# Conception Alignment Review

## Status

This review compares the original `deep-research-report.md` conception with the
current v1.0.0 repository state.

The short version: v1.0.0 successfully proves the local, policy-gated harness
foundation. It does not yet prove the full applied-AI system originally
envisioned, because live model execution, production retrieval, operator
surfaces, MCP, retention, and enterprise-grade evidence remain deliberately
deferred.

The original conception should remain the north star, but future work should not
copy its old MVP/v1/v2 labels. The real release history is now v0.1.0 through v1.0.0,
with v1.0.0 closing the stable local CLI/runtime baseline.

## What This Repo Proves

- A framework-agnostic Python CLI core with no LangGraph, MCP, or provider SDK
  dependency in the primary runtime path.
- Versioned public inputs for `config.v2`, `task.v2`, `policy.v2`, and
  `template.v2`, plus migration evidence for readable v1 inputs.
- Policy-mediated context inclusion, tool execution, provider input, provider
  use, template application, and separate `git_commit` approval.
- Inspectable context manifests with sensitivity labels, included and rejected
  evidence, lexical retrieval, local dense fixture retrieval, and provider-input
  bindings back to manifest items.
- Human approval records, checkpoints, and drift checks for risky actions.
- Append-only run events, summaries, artifact indexes, security findings,
  provider-call audit artifacts, and JSON/Markdown/SARIF exports.
- Bundled template registry metadata, bundled Python templates, and validation
  evidence for clean template application.
- Local evals, adversarial checks, benchmark-shaped sample packs, release
  readiness, package checks, pre-commit, CI, and Docker demo packaging.

## Coverage Matrix

| Deep research area | Current state | Gap |
| --- | --- | --- |
| CLI-first local runtime | Strong | CLI surface is broader than the original MVP contract and is now stable at v1.0.0. |
| Framework-agnostic core | Strong | LangGraph is only an optional boundary proof; MCP is still a stub. |
| Typed task and policy contracts | Strong | Current schemas are JSON/Pydantic rather than the YAML examples from the report. |
| Tool mediation and approvals | Strong | Core read/search/test/patch/template/provider/git flows are policy mediated. |
| Explicit context packs | Strong | Context manifests exist, but retrieval quality is still local and fixture-grade. |
| Append-only auditability | Strong | Run events and artifacts are inspectable; retention profiles are not implemented. |
| Provider-neutral model interface | Partial | Mock and recorded fixtures exist; live provider execution is intentionally disabled. |
| Structured model outputs | Partial | Tool-call artifacts are typed, but malformed live model output is not yet a real path. |
| Template database and reuse | Partial | Bundled SQLite registry exists; external catalogs and non-Python expansion are absent. |
| Evals before UI | Partial | Local evals exist; original quantitative success criteria are not yet measured at scale. |
| Qdrant retrieval backend | Partial | Optional dependencies are detected, but Qdrant/FastEmbed retrieval is smoke-only. |
| OpenTelemetry | Minimal | Trace ids are deterministic helper values, not exported OpenTelemetry spans or dashboards. |
| MCP adapter | Missing | `mcp_adapter` fails clearly as unsupported. |
| Web API and approval UI | Missing | Correctly deferred until the CLI/runtime baseline was stable. |
| Enterprise/compliance controls | Partial | Policy, audit, approval, and docs boundaries exist; identity, attestation, DLP, and hardened sandboxing do not. |
| Supply-chain evidence | Partial | Pre-commit, CI, package checks, and optional advisory evidence exist; Semgrep, Trivy, SBOM generation, Dependabot, and SARIF upload are not complete required gates. |

## Drift Diagnosis

The main drift is not architectural collapse. The package boundaries mostly match
the original report. The drift is that the project matured into a rigorous local
control-plane release before it became a live applied-AI runtime.

Important drift points:

- The original report's MVP/v1/v2 milestone labels no longer map to the actual
  release history. The project now has v0.1.0, v0.2.0, v0.3.0, and v1.0.0/v1.0.0.
- Some report-shaped modules are boundary placeholders rather than implemented
  systems, especially MCP, OpenTelemetry, and production Qdrant.
- The current provider path is auditable and well controlled, but still relies
  on deterministic mock behavior or recorded fixtures by default.
- The eval suite proves invariants and workflow safety, not broad task
  competence against the original 8/10 dry-run and 6/10 write-enabled success
  targets.
- The public docs correctly avoid unsupported claims, but the original product
  ambition now lives mostly in `deep-research-report.md` and roadmap bullets
  instead of an explicit alignment plan.

## Remaining Work To Reach The Conception

The highest-value remaining work is ordered below. This is the path from
"stable local harness" to the originally envisioned applied-AI system.

1. Live provider execution behind policy gates.
   Add an opt-in live provider path with schema-validated outputs, provider-use
   approval, provider-input hard-deny enforcement, redacted prompt/response
   evidence, and deterministic recorded fixtures for normal tests.

2. Structured model-output boundary.
   Treat model responses as untrusted data. Validate them against public action
   schemas before any tool execution, record malformed-output failures, and
   ensure provider adapters cannot bypass the native policy/runtime boundary.

3. Retention and redaction profiles.
   Add `dev`, `ci`, and `enterprise` retention profiles for run artifacts.
   Default to redacted storage for prompts, responses, and external evidence.

4. Retrieval hardening.
   Promote the current local dense fixture into a real optional Qdrant/FastEmbed
   backend with deterministic fallback evidence and no remote embeddings by
   default.

5. Operator surfaces.
   Add a local web API and then an approval/inspection UI over existing run,
   context, approval, provider, and export artifacts. This should expose the
   control plane, not replace it.

6. MCP boundary.
   Add read-only MCP resources and prompts first. Tool execution through MCP
   should remain a later, explicitly approval-gated capability.

7. Security and supply-chain evidence.
   Convert optional Gitleaks/CycloneDX visibility into stronger required or
   release-readiness evidence where practical, then add Semgrep, Trivy,
   Dependabot, `SECURITY.md`, and a docs build workflow.

8. Evaluation scale.
   Add fixture suites that measure task success, policy violation rate,
   approval compliance, context precision, reproducibility, latency, and audit
   completeness. Only then compare against larger public benchmark adapters.

## Roadmap

The recommended next version is v1.1.0: live provider and structured-output
alignment. That is the most direct fix for the concept drift because the
original project was conceived as an LLM-powered software-engineering harness,
while the current release is primarily a deterministic, auditable control-plane
baseline.

v1.1.0 should not add web UI, MCP execution, multi-agent orchestration, or
enterprise/compliance claims. Those become credible only after the live provider
path is policy-safe, inspectable, and covered by evals.
