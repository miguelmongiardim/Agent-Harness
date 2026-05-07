# Conception Alignment Review

## Status

This review compares the original project conception with the current post-v1.9
repository state.

The short version: the repository has grown from the v1.0.0 local CLI/runtime
foundation into a local evidence and review platform with provider-core gates,
local retrieval, operator inspection, template and skill packs, read-only MCP
evidence, sequential orchestration, governance exports, and compliance evidence
packaging. It still does not claim hosted platform behavior, enterprise
readiness, formal compliance certification, broad benchmark success, or
production retrieval deployment.

The original conception should remain the north star, but future work should not
copy its old MVP/v1/v2 labels or stale next-version guidance. The durable
release history now runs from v0.1.0 through v1.9.0, with near-term work focused
on CI/release hardening and public-doc consistency unless a new PRD chooses a
larger product track.

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

| Conception area | Current state | Gap |
| --- | --- | --- |
| CLI-first local runtime | Strong | CLI surface is broader than the original MVP contract and is now stable at v1.0.0. |
| Framework-agnostic core | Strong | LangGraph is only an optional boundary proof; MCP is still a stub. |
| Typed task and policy contracts | Strong | Current schemas are JSON/Pydantic rather than the early YAML examples. |
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

The main drift is not architectural collapse. The package boundaries mostly
match the intended ownership model. The drift is that the project matured into
a rigorous local control-plane and evidence-packaging tool before it became a
broad live applied-AI runtime.

Important drift points:

- The original MVP/v1/v2 milestone labels no longer map to the actual
  release history. The project now has v0.1.0, v0.2.0, v0.3.0, and v1.0.0/v1.0.0.
- Some planned modules are boundary placeholders rather than implemented
  systems, especially MCP, OpenTelemetry, and production Qdrant.
- The current provider path is auditable and well controlled, but still relies
  on deterministic mock behavior or recorded fixtures by default.
- The eval suite proves invariants and workflow safety, not broad task
  competence against the original 8/10 dry-run and 6/10 write-enabled success
  targets.
- The public docs correctly avoid unsupported claims, but the original product
  ambition is still split across roadmap bullets and this alignment plan.

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

The immediate maintenance direction is CI/release hardening and docs
consistency. That keeps the current local evidence platform reliable while the
next larger product track is chosen deliberately.

The next product-track PRD should choose one narrow boundary from the remaining
work above. It should not add hosted platform behavior, MCP execution,
production retrieval, or enterprise/compliance claims without a separate
security, identity, approval, and release-evidence plan.
