# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using V2 config, task, policy, and template inputs; a deterministic mock agent;
configured provider profiles; provider-input policy gates; strict provider
action envelopes; opt-in OpenAI-compatible live smoke; redacted provider-call
evidence; local retrieval indexes, hybrid retrieval, qdrant-local evidence,
retrieval scorecards, approval-bound template application, separate
`git_commit` approval, packaged benchmark adapters, a single-case benchmark
comparison artifact for the local terminal sample, validated bundled and
configured local skill discovery, task-requested skill resolution,
template-recommended skill evidence, policy-gated skill context evidence,
skill manifest run evidence, a skills workflow demo, V8 skill release gates,
provider audit demos, release-readiness reports, audit logs, evals, an
optional LangGraph boundary proof, and reproducible artifacts.

## v1.0.0 Status

v1.0.0 closes the V3 release-maturity track. The stable local OSS scope covers
core CLI behavior, public schema compatibility policy, package and
clean-install evidence, reproducible demos, Docker demo packaging, pre-commit
and CI hygiene, bundled template validation, and release-readiness evidence.

The detailed V3 plan lives in [plans/agent-harness-v3.md](../plans/agent-harness-v3.md).

The current conception alignment review lives in
[docs/conception-alignment.md](conception-alignment.md). It compares the
original `deep-research-report.md` vision with the v1.0.0 implementation and
defines the remaining drift.

## v1.1.0 Status

v1.1.0 closes the V4 Provider Core track:
[docs/prd-agent-harness-v4.md](prd-agent-harness-v4.md) and
[plans/agent-harness-v4.md](../plans/agent-harness-v4.md). It adds strict
provider action envelopes, profile validation, opt-in OpenAI-compatible live
smoke, provider-call evidence, redacted prompt/response artifacts,
provider-core evals, and setup/safety docs.

V4 does not promote fixture capture tooling, retention profiles, web UI, MCP
execution, multi-agent orchestration, production Qdrant server mode, Anthropic
live support, or enterprise readiness.

## v1.2.0 Status

v1.2.0 closes the V5 local-first retrieval hardening track:
[docs/prd-agent-harness-v5.md](prd-agent-harness-v5.md) and
[plans/agent-harness-v5.md](../plans/agent-harness-v5.md). The track keeps
base-install lexical retrieval available while adding local index lifecycle
commands, deterministic dense test embeddings, local-only FastEmbed behavior,
persistent local Qdrant storage, loopback-only Qdrant server developer support,
hybrid retrieval, scorecards, a local retrieval quality demo, and
policy-filtered context manifest evidence.

Cloud Qdrant, hosted embedding providers, remote embeddings, remote embedding
APIs, remote vector databases, API-key-backed Qdrant endpoints, HTTPS remote
Qdrant endpoints, production Qdrant server operation, MCP, API/UI surfaces,
multi-agent workflows, enterprise retrieval claims, and compliance-ready
retrieval claims remain future-only and are not V5 behavior.

## v1.3.0 Status

v1.3.0 is the V6 local operator surface target:
[docs/prd-agent-harness-v6.md](prd-agent-harness-v6.md) and
[plans/agent-harness-v6.md](../plans/agent-harness-v6.md). The implemented
track adds a loopback-only API and packaged static UI for inspecting existing
run artifacts and approving or denying existing pending approvals through the
same approval service as the CLI. Release readiness records operator evidence
for app import, API smoke, token enforcement, host rejection, approval binding,
and static UI packaging.

V6 does not target hosted API behavior, remote web UI operation, multi-user
authentication, an enterprise control plane, cloud deployment, production web
service operation, compliance readiness, MCP, multi-agent orchestration, run
creation, config editing, direct patch application, direct git commit creation,
or direct provider execution.

## v1.4.0 Status

v1.4.0 is the V7 Template Pack System track:
[docs/template-pack-system.md](template-pack-system.md),
[docs/prd-agent-harness-v7.md](prd-agent-harness-v7.md), and
[plans/agent-harness-v7.md](../plans/agent-harness-v7.md). The implemented
track keeps template packs local-first and inspectable through `template.v2.toml`
pack manifests, explicit local directories, deterministic parameter
substitution, dry-run and preview-diff planning, clean empty-target apply
evidence, bundled workflow packs, and release-readiness gates for bundled pack
validation, dry-run, clean apply, generated example schemas, docs, application
evidence, and remote catalog default rejection.

Remote template catalogs, template marketplace behavior, template signing,
organization template catalogs, cloud template registries, executable lifecycle
hooks, script execution, enterprise template governance, and conditional file
inclusion remain future-only and are not V7 behavior.

## v1.5.0 Status

v1.5.0 is the V8 Skills System release:
[docs/skills-system.md](skills-system.md),
[docs/prd-agent-harness-v8.md](prd-agent-harness-v8.md), and
[plans/agent-harness-v8.md](../plans/agent-harness-v8.md). Implemented slices
add local, versioned, validated Markdown workflow guidance with deterministic
provenance for bundled and explicitly configured local skill sources,
task-requested skill resolution, template-recommended skill evidence, and
context-manifest provenance for accepted or rejected task-requested guidance.
Runs that use skills now emit `skill_manifest.v1` evidence and expose it
through run summaries, artifact indexes, inspect output, operator run detail,
and eval expected-skill assertions. The V8 golden path is implemented under
`examples/skills_workflow/`, and release readiness verifies required bundled
skill validation, registry behavior, task resolution, context provenance,
`skill_manifest.v1`, inspect output, skills docs, and demo evidence. Skills are
guidance for how work should be performed; they are not tools, templates,
policy, approvals, provider profiles, or executable code.

Remote skill catalogs, skill marketplace behavior, skill signing, hosted skill
services, enterprise skill registries, organization-wide skill governance,
centralized skill governance, skill installation from network locations, and
automatic execution from skills remain future-only and are not V8 behavior.

## v1.6.0 Status

v1.6.0 is the V9 MCP Boundary release:
[docs/mcp-boundary.md](mcp-boundary.md),
[docs/prd-agent-harness-v9.md](prd-agent-harness-v9.md), and
[plans/agent-harness-v9.md](../plans/agent-harness-v9.md). The implemented
track adds a local, optional, read-only MCP boundary under `agent_harness.mcp`
for exposing selected Agent Harness evidence through MCP resources and review
prompts.

V9 is not a runtime adapter. The existing `agent_harness.runtimes.mcp_adapter`
remains unsupported while V9 proves resources, prompts, stdio transport,
policy-filtered artifacts, release-readiness gates, and MCP access evidence.
MCP tools, write-capable MCP, MCP approval actions, MCP run execution, MCP
provider execution, Streamable HTTP MCP, hosted MCP service, remote MCP
gateways, enterprise MCP registries, and multi-agent orchestration remain
future-only.

## v1.7.x V11 Planning And Evidence

V11 planning is captured in
[docs/prd-agent-harness-v11.md](prd-agent-harness-v11.md) and
[plans/agent-harness-v11.md](../plans/agent-harness-v11.md). It describes
local, sequential, policy-mediated orchestration over normal child task runs.
The current implementation supports `agent-harness orchestration run <spec>
--dry-run`, `approve`, `resume`, and `inspect` for explicitly enabled
`policy.v2.orchestration` profiles. It materializes normal child `task.v2`
artifacts, records aggregate orchestration evidence, enforces role ceilings,
pauses risky plans for supervisor approval, writes generated dependency
handoffs, prevents provider default inheritance, uses existing provider gates
for explicit provider children, stops on child pause/failure, and resumes
without rerunning completed children. It also writes stable orchestration JSON
exports and exposes read-only MCP resources for orchestration summary, manifest,
events, children, and handoffs with metadata-only access logs. The V11 golden
path lives in `examples/orchestration_workflow/`, and release readiness verifies
orchestration demo, policy, artifact, inspect/export, MCP resource-read, and
access-log gates. Operator UI support and enterprise governance remain
future-only. V11 does not support hosted APIs. Parallel multi-agent
orchestration remains future-only. Nested orchestration remains future-only.
MCP execution for multi-agent orchestration remains future-only.

The V11 multi-agent complexity benchmark is planned separately in
[docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md](prd-agent-harness-v11-multi-agent-complexity-benchmark.md)
and
[plans/agent-harness-v11-multi-agent-complexity-benchmark.md](../plans/agent-harness-v11-multi-agent-complexity-benchmark.md).
The implemented comparison path supports
`agent-harness benchmark compare local-samples terminal-readonly-inspect` for a
single case and `agent-harness benchmark compare local-samples` for the bundled
pack. It performs baseline-first comparison against sequential generated
orchestration modes: planner -> implementer, planner -> implementer ->
reviewer, and tester mode only for bundled cases with executable
`test_commands`. It writes `benchmark_comparison_result.v1` and
`benchmark_comparison_suite.v1` with links to baseline run exports,
orchestration exports, child run summaries, per-case artifacts, mode
eligibility, and skip reasons. It also records evidence-derived metrics for task success, test
evidence, policy violations, approval state, child/tool and handoff counts,
handoff size, coordination overhead, artifact completeness, failure
attribution, handoff usefulness, conservative role recommendations, and
explicit unavailable token/runtime/cost values. Role recommendations include
reason codes and supporting metric names, and they do not alter policy defaults
or generated orchestration role lists. `agent-harness eval` includes local
comparison evidence that fails when compared cases lack inspectable baselines.
Broader-pack allowlists and role-default promotion remain future scope.
Role-count expansion requires comparative outcome evidence before
recommendation or promotion.

v1.7.1 finalizes the local multi-agent complexity benchmark comparison track
as release evidence only. It does not add hosted benchmark execution, external
datasets, configurable broader-pack allowlists, or automatic role-default
promotion.

## v1.8.0 In Progress

V12 implementation has started with a local governance summary, blocking
governance check, report generation, and explicit export writing.

The V12 Local Governance Console planning artifacts are
[docs/prd-agent-harness-v12-local-governance-console.md](prd-agent-harness-v12-local-governance-console.md)
and
[plans/agent-harness-v12-local-governance-console.md](../plans/agent-harness-v12-local-governance-console.md).
Phase 3 implements `agent-harness governance summary`, `check`, `report`, and
`export`. The summary emits `governance_summary.v1` data from local config,
default policy, run-summary artifacts, domain status classification, run
counts, initial finding counts, safe diagnostics, and project-relative evidence
references. The check emits `governance_check.v1`, returns documented
blocking/advisory exit codes, rejects unsafe artifact references, and reports
raw provider payload artifacts without exposing their contents. The report and
export commands emit `governance_report.v1`, `governance_index.v1`, and
`governance_findings.v1` artifacts with safe project-relative evidence refs,
content hashes for included evidence, and raw provider payload artifacts marked
excluded. Operator API, operator UI, and release-readiness gates remain
future-only.
Hosted governance, enterprise governance control planes, multi-tenant admin,
cloud deployment, compliance readiness, SOC2 readiness, ISO readiness, and
formal certification remain future-only.

## v1.9.0 In Progress

V1.9 Compliance Evidence Pack planning lives in
[docs/compliance-evidence-pack.md](compliance-evidence-pack.md),
[docs/prd-agent-harness-v1.9-compliance-evidence-pack.md](prd-agent-harness-v1.9-compliance-evidence-pack.md),
and
[plans/agent-harness-v1.9-compliance-evidence-pack.md](../plans/agent-harness-v1.9-compliance-evidence-pack.md).

The planned pack depends on completed V12 governance exports:
`governance_summary.v1`, `governance_report.v1`, `governance_index.v1`, and
`governance_findings.v1`. Phase 4 adds evidence command discovery,
prerequisite validation for missing V12 governance exports,
`evidence pack --format json` generation of canonical evidence pack, manifest,
index, findings, control mapping, and checksum files, redaction-safe artifact
indexing from V12 governance indexes, and review-only control mapping Markdown
for bundle output. Full Markdown pack presentation, archive creation, operator
API/UI routes, and release-readiness gates remain
unimplemented until later phases add tested behavior.
The implementation includes redaction-safe artifact indexing for portable
review bundles.

The planned pack packages existing governance evidence for review and audit
preparation. It does not rebuild governance aggregation, run workflows, call
providers, execute scanners, or create release evidence. It does not certify compliance.
The pack is not legal, regulatory, security, or organizational certification.

## Release Maintenance Priorities

- Preserve the v1.0.0 compatibility and deprecation contract.
- Keep release readiness as the control surface for package, docs, demos,
  templates, changelog, CI, and release artifacts.
- Maintain local and Docker provider-audit golden paths.
- Keep every bundled template validated and allow clean empty-destination scaffolding
  without weakening overwrite protections.
- Keep pre-commit and CI gates stable for routine changes.

## Later Possibilities

- Add hosted operator deployment only after a separate security and identity
  plan exists.
- Add multi-user authentication only after the local operator surface is
  complete and audited.
- Add external template catalogs and remote template discovery.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Expand policy-mediated orchestration beyond the current local sequential
  dry-run supervisor.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
- Add cloud or production Qdrant modes and deployment-scale retrieval tuning.
- Add hosted or remote retrieval providers.
- After V9, consider MCP tools or hosted MCP only with a separate policy,
  approval, identity, and release-evidence plan.
- Add enterprise/compliance readiness work, including production identity,
  centralized secrets management, hardened sandboxing, and attestation.
