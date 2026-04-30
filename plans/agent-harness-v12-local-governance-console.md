# Plan: Agent Harness V12 Local Governance Console

> Source PRD:
> [docs/prd-agent-harness-v12-local-governance-console.md](../docs/prd-agent-harness-v12-local-governance-console.md)

This plan follows the PRD -> Plan -> TDD workflow. It is intentionally limited
to planning; do not implement these phases until a separate implementation
request starts TDD execution.

V12 targets `v1.8.0`. The feature is a local governance evidence browser and
reporting surface over existing artifacts, not a hosted admin platform,
enterprise control plane, or compliance product.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness governance summary`, `report
  --format markdown|json`, `check`, and `export --output <path>`. Do not add
  `agent-harness governance serve`; use existing `agent-harness serve`.
- **Key models**: add governance summary, governance report, governance index,
  governance finding, domain status, domain payload, and check result contracts
  under the governance boundary.
- **Schema**: introduce `governance_summary.v1`, `governance_report.v1`,
  `governance_index.v1`, and `governance_finding.v1` in
  `agent_harness.governance.schema`.
- **Storage**: read only configured artifact roots and known evidence paths.
  Write exports only under the user-selected governance export directory,
  normally `.agent-harness/governance/`.
- **Runtime boundary**: governance observes existing artifacts and never
  executes runs, providers, templates, MCP tools, or orchestration children.
- **Policy boundary**: policy remains the permission ceiling. Governance can
  report policy state and violations but cannot widen permissions or edit
  policy.
- **Approval model**: governance reads approval evidence and findings; approval
  mutation remains in the existing run approval surfaces.
- **Audit model**: governance indexes referenced evidence with safe
  project-relative paths, content hashes, schema versions, and redaction
  status. It never copies raw provider payloads or secrets.
- **Operator boundary**: extend the existing local operator app with
  token-protected read-only governance routes and a packaged static Governance
  section.
- **External service boundary**: V12 is local and artifact-backed. It requires
  no network, hosted service, remote dashboard, multi-user identity, or
  compliance backend.

---

## Phase 0: V12 Scope Is Documented And Guarded

**User stories covered**

- Story 18: documentation reviewer can prevent unsupported governance and
  compliance claims.
- Story 17: release maintainer can see how V12 leads into later compliance
  evidence without claiming readiness.

**Observable behaviors**

- V12 PRD and vertical implementation plan exist as durable planning artifacts.
- Public docs can reference V12 as planned work without claiming it is
  implemented before feature evidence exists.
- Docs checks can reject unsupported implemented claims for hosted governance,
  enterprise control planes, multi-tenant admin, compliance readiness, SOC2
  readiness, ISO readiness, cloud deployment, and formal compliance
  certification.

**First RED test**

- Add a docs-check integration test that fails when current capability docs say
  Agent Harness provides hosted governance, enterprise governance control
  planes, multi-tenant admin, compliance readiness, SOC2 readiness, ISO
  readiness, cloud deployment, or formal compliance certification outside
  roadmap/future language.

### What to build

Add the V12 PRD and plan, then extend docs-claim guard behavior only enough to
keep public documentation honest while implementation proceeds. Do not add
governance CLI, schemas, API routes, or UI behavior in this phase.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v12-local-governance-console.md` exists and
      follows the repo PRD template.
- [x] `plans/agent-harness-v12-local-governance-console.md` exists and uses
      vertical tracer-bullet phases.
- [x] Docs checks reject unsupported governance and compliance claims.
- [x] README and roadmap identify V12 as planned until implementation and
      release evidence exist.
- [x] No governance runtime, CLI, API, UI, release-readiness, or export
      behavior is added.

### Phase 0 implementation notes

- Added `unsupported_governance_scope_claim` docs-check coverage for hosted
  governance, enterprise governance control planes, multi-tenant admin,
  compliance readiness, SOC2 readiness, ISO readiness, cloud deployment, and
  formal compliance certification claims outside roadmap/future language.
- README and roadmap now link the V12 PRD/plan and describe V12 as planned,
  not implemented.
- Scope stayed documentation-only: no governance CLI, schema, API, UI,
  release-readiness, or export behavior was added.

### Out of scope

- Governance schemas.
- Governance CLI commands.
- Governance aggregation.
- Operator API/UI changes.
- Release-readiness governance gates.

---

## Phase 1: User Can Generate A Minimal Governance Summary

**User stories covered**

- Story 1: reviewer gets one local governance summary.
- Story 4: optional absent domains are represented clearly.
- Story 5: enabled domains missing evidence are distinguished from absence.
- Story 6: malformed evidence becomes a diagnostic instead of a crash.

**Observable behaviors**

- `agent-harness governance summary` works on a clean local project.
- The command reads config, policy, and run storage through existing loaders.
- The summary emits `governance_summary.v1` data with domain statuses,
  policy profile information, run counts, and initial finding counts.
- Optional domains without artifacts report `not_present`.
- Malformed required summary inputs produce safe diagnostics and governance
  findings.

**First RED test**

- An integration test seeds a project with a default policy and one dry-run
  task, invokes `agent-harness governance summary`, and asserts
  `governance_summary.v1`, policy domain `present`, run domain `present`,
  optional domains `not_present`, safe project-relative workspace metadata, and
  no raw file contents.

### What to build

Create the smallest end-to-end governance path: boundary-owned schema models,
domain status classification, known artifact-root access, policy/run
aggregation, safe diagnostics, and the `summary` CLI command. Keep the first
slice narrow enough that reports, exports, API routes, and release readiness
are not needed yet.

### Acceptance criteria

- [x] `agent-harness governance --help` exposes the command family.
- [x] `governance summary` returns valid `governance_summary.v1` data.
- [x] Policy and run domains aggregate from existing config, policy, and run
      storage.
- [x] Optional absent domains report `not_present`.
- [x] Missing and malformed required artifacts become diagnostics and
      findings without crashing.
- [x] Artifact paths in summary-adjacent diagnostics are safe project-relative
      paths.

### Phase 1 implementation notes

- Added `agent_harness.governance` with boundary-owned schema models and a
  minimal summary aggregator.
- Added `agent-harness governance summary`, which emits
  `governance_summary.v1` JSON from local config, default policy, and known
  run-summary artifacts.
- Optional absent domains report `not_present`; empty security finding files
  do not make security governance present.
- Missing policy evidence and malformed run summaries produce safe diagnostics
  and `governance_finding.v1` records without leaking raw artifact contents or
  absolute machine-local paths.
- Scope stayed Phase 1-only: no report, check, export, operator API/UI, or
  release-readiness governance behavior was added.

### Out of scope

- Markdown/JSON report rendering.
- Export files.
- Operator API/UI.
- Release readiness integration.
- Deep aggregation for provider, retrieval, template, skill, MCP, or
  orchestration domains.

---

## Phase 2: Blocking Governance Checks Are Redaction-Safe

**User stories covered**

- Story 2: governance checks fail only on blocking findings.
- Story 3: reports and checks do not expose secrets or raw provider payloads.
- Story 9: provider governance is inspectable without leaking payloads.
- Story 15: normalized findings are comparable across domains.

**Observable behaviors**

- `agent-harness governance check` returns documented exit codes.
- Critical findings block by default.
- Advisory findings are visible but do not fail the command unless
  `blocks_release` is true.
- Seeded raw provider payload artifacts produce a governance finding without
  exposing contents.
- Path traversal, absolute local paths, and malformed evidence produce
  normalized findings.

**First RED test**

- An adversarial test seeds a raw provider payload artifact, an unsafe artifact
  reference, and an advisory docs finding, then runs `governance check` and
  asserts exit code `1`, redacted output, critical blocking findings, advisory
  visibility, and no leaked payload text.

### What to build

Add the governance finding model, severity/blocking rules, check result
handling, exit code mapping, redaction filters, and safety checks for provider
payload artifacts and unsafe artifact references. Extend provider, approval,
and security aggregation only as needed to exercise the check behavior through
public artifacts.

### Acceptance criteria

- [x] Exit code `0` means no blocking findings.
- [x] Exit code `1` means blocking findings exist.
- [x] Exit code `2` means invalid input, config, or artifact root.
- [x] Exit code `3` means internal error.
- [x] Critical findings block release by default.
- [x] Raw provider payload contents, API keys, env var values, raw headers, and
      unredacted sensitive context do not appear in output.
- [x] Unsafe artifact references are rejected and mapped to
      `governance_finding.v1`.

### Phase 2 implementation notes

- Added `agent-harness governance check`, which emits `governance_check.v1`
  JSON and maps exit codes `0`, `1`, `2`, and `3`.
- Added redaction-safe blocking findings for raw provider payload artifacts and
  unsafe run-summary artifact references without reading or copying raw payload
  contents.
- Existing docs-check findings are carried as visible advisory findings and do
  not fail the command unless a future phase marks them blocking.
- Invalid config or artifact-root input returns a generic redaction-safe
  diagnostic instead of exposing raw config values or machine-local paths.
- Scope stayed Phase 2-only: no report, export, operator API/UI, or
  release-readiness governance behavior was added.

### Out of scope

- Report/export layout.
- Operator API/UI.
- Release readiness gates.
- Policy-configurable finding severity overrides beyond the default mapping.

---

## Phase 3: Reviewer Can Produce Reports And Export Evidence

**User stories covered**

- Story 1: reviewer can inspect aggregate governance evidence.
- Story 3: reports are redaction-safe.
- Story 15: findings are normalized across domains.
- Story 17: governance artifacts can feed release readiness and later
  compliance evidence.

**Observable behaviors**

- `agent-harness governance report --format markdown` produces a Markdown
  report with the required governance sections.
- `agent-harness governance report --format json` produces a
  `governance_report.v1` payload.
- `agent-harness governance export --output .agent-harness/governance/` writes
  the documented file layout.
- `governance_index.v1` references every included evidence artifact through
  safe metadata.
- Exports are deterministic where practical and do not copy raw provider
  payloads or arbitrary workspace files.

**First RED test**

- An integration test runs a provider-audit fixture, generates Markdown and
  JSON reports, exports to `.agent-harness/governance/`, and asserts file
  names, schema versions, required sections, safe evidence refs, content hashes,
  and absence of raw provider payload content.

### What to build

Add report rendering, JSON report payloads, export writing, governance index
construction, evidence hash recording, and deterministic output ordering for
public artifacts. The report should use the same aggregation and finding
pipeline as summary and check.

### Acceptance criteria

- [x] Markdown report includes policy, run, approval, provider, retrieval,
      template, skill, MCP, multi-agent, security, release readiness, and
      unsupported claim sections.
- [x] JSON report validates as `governance_report.v1`.
- [x] Export writes `governance_summary.v1.json`,
      `governance_report.v1.md`, `governance_report.v1.json`,
      `governance_index.v1.json`, and `governance_findings.v1.json`.
- [x] `governance_index.v1` entries include artifact type, safe path, content
      hash, source run id where applicable, schema version, redaction status,
      and inclusion status.
- [x] Exports do not copy or expose raw provider payloads, secrets, absolute
      local paths, raw Qdrant internals, or arbitrary workspace files.

### Phase 3 implementation notes

- Added `agent-harness governance report --format markdown|json`, backed by
  the same summary and check aggregation used by earlier phases.
- Added `agent-harness governance export --output <path>`, which writes the
  documented five-file layout only when explicitly requested.
- Added `governance_report.v1`, `governance_index.v1`,
  `governance_findings.v1`, and export result contracts under the governance
  boundary.
- Governance index entries cover known safe config, policy, run, provider,
  docs-check, and redacted provider evidence with project-relative paths,
  hashes for included evidence, source run ids where applicable, schema
  versions where present, redaction status, and inclusion status.
- Raw provider payload artifacts are represented as excluded metadata and are
  not copied into exports or rendered into report contents.
- Scope stayed Phase 3-only: no operator API/UI, release-readiness gate, or
  compliance control mapping was added.

### Out of scope

- Operator API/UI.
- Release readiness integration.
- Compliance control mapping.

---

## Phase 4: Optional Domains Are Aggregated With Precise Status

**User stories covered**

- Story 7: policy governance answers allow/deny/approval questions.
- Story 8: approval governance distinguishes decision states.
- Story 10: retrieval governance explains context selection.
- Story 11: template governance shows installed and applied templates.
- Story 12: skill governance shows local validated guidance.
- Story 13: MCP governance shows read-only resources and denials.
- Story 14: multi-agent governance shows roles, boundaries, handoffs, and
  complexity evidence.
- Story 15: security findings are normalized.

**Observable behaviors**

- Governance summary/report/check/export classify every domain using the domain
  status enum.
- Retrieval, template, skill, MCP, orchestration, security, and release
  readiness evidence are aggregated when present.
- An unused optional domain reports `not_present`.
- An enabled or used domain with missing required evidence reports
  `missing_evidence`.
- Malformed optional evidence reports `malformed_evidence` and adds a finding.

**First RED test**

- An integration test seeds fixtures for retrieval scorecards, template
  applications, skill manifests, MCP access logs, orchestration summaries, and
  malformed optional evidence, then asserts domain statuses, counts, findings,
  and safe report/index references.

### What to build

Expand the governance aggregation pipeline domain by domain, but keep the
public behavior focused on classification and safe summaries. Reuse existing
domain-owned loaders or public artifacts where they exist. Add only the minimum
new extraction needed to answer the PRD questions for each domain.

### Acceptance criteria

- [ ] Policy governance reports profiles, default profile, provider-input
      matrix, sensitivity behavior, approval-gated actions, denied actions,
      scanner thresholds, template capability permissions, skill rules, MCP
      permissions, and orchestration permissions where present.
- [ ] Approval governance reports pending, approved, denied, stale,
      failed-binding, and policy-denied counts where evidence exists.
- [ ] Retrieval governance reports index/backend/embedding/provenance/scorecard
      evidence and local-first flags.
- [ ] Template governance reports bundled/local templates, validation, and
      `template_application.v1` evidence.
- [ ] Skill governance reports installed skills, validation, sources, risks,
      and text-only boundaries.
- [ ] MCP governance reports resources, prompts, denial evidence, policy
      filtering, and metadata-only access logs.
- [ ] Multi-agent governance reports orchestration roles, boundaries, handoffs,
      approvals, timelines, and complexity benchmark evidence.
- [ ] Security findings are normalized into governance finding/count summaries.

### Out of scope

- Operator UI rendering.
- Release readiness gates.
- New domain execution behavior.
- New MCP, orchestration, retrieval, template, or skill capabilities.

---

## Phase 5: Operator API Exposes Read-Only Governance Routes

**User stories covered**

- Story 1: reviewer can inspect governance evidence through one local surface.
- Story 3: API payloads are redaction-safe.
- Story 16: operator UI can use existing local server routes.

**Observable behaviors**

- The existing operator app exposes `/api/v1/governance/*` routes.
- Every governance route requires `X-Agent-Harness-Operator-Token`.
- Routes are read-only and return safe domain payloads backed by governance
  aggregation.
- Missing domains report `not_present`; malformed evidence reports
  `malformed_evidence`.
- Unsupported write methods do not mutate anything.

**First RED test**

- An operator API integration test calls every governance route without a
  token, with an invalid token, and with a valid token, then asserts token
  enforcement, schema versions, read-only behavior, safe domain statuses, and
  no leaked raw provider payloads.

### What to build

Wire the governance aggregation boundary into the existing operator app as
read-only routes for overview, policies, runs, approvals, providers,
retrieval, templates, skills, MCP, multi-agent, security findings, and release
readiness. Preserve the existing catch-all behavior for unsupported mutation
routes.

### Acceptance criteria

- [ ] All governance routes require the operator token.
- [ ] Routes return safe JSON payloads from the governance boundary.
- [ ] Routes do not mutate runs, approvals, policies, configs, artifacts, or
      governance exports.
- [ ] Routes do not expose secrets, raw provider payloads, raw headers,
      unredacted sensitive context, arbitrary workspace files, or absolute
      local paths.
- [ ] Malformed evidence becomes a safe API domain status or finding rather
      than an unhandled server error.

### Out of scope

- Governance UI tab.
- Approval mutation in governance routes.
- Any new server command.
- Hosted API behavior.

---

## Phase 6: Operator UI Provides A Governance Evidence Browser

**User stories covered**

- Story 16: operator UI user can browse governance evidence locally.
- Story 3: UI does not expose unsafe content.
- Story 4 and Story 5: UI distinguishes absent and missing evidence.

**Observable behaviors**

- The packaged operator UI has a Governance section.
- Governance views use only local `/api/v1/governance/*` routes.
- The UI displays overview, policies, runs, approvals, providers, retrieval,
  templates, skills, MCP, multi-agent, security findings, release readiness,
  and exports views.
- The UI has no remote CDN/API dependency.
- The Governance section cannot create, approve, deny, delete, edit, rerun, or
  mutate anything.

**First RED test**

- An operator UI smoke test loads the packaged JavaScript and HTML, asserts a
  Governance section exists, asserts only local governance API routes are used,
  asserts forbidden remote markers are absent, and asserts no governance view
  posts mutation requests.

### What to build

Extend the existing vanilla packaged UI with a governance navigation mode and
read-only renderers for governance domain payloads. Keep the design consistent
with the existing local operator UI and avoid turning the governance browser
into a second approval surface.

### Acceptance criteria

- [ ] Governance section is visible in the packaged local UI.
- [ ] Governance UI displays local-only status.
- [ ] Governance UI renders domain status and finding summaries.
- [ ] Governance UI links or references source artifact metadata only through
      safe project-relative references.
- [ ] Governance UI contains no external assets, CDN links, analytics, or
      remote API calls.
- [ ] Governance UI performs no mutation requests.

### Out of scope

- Rich dashboards or charts requiring a frontend build.
- Browser persistence for governance state.
- Approval decisions inside governance views.
- Hosted or remote UI operation.

---

## Phase 7: Release Readiness Requires Governance Evidence

**User stories covered**

- Story 2: blocking findings fail release checks.
- Story 17: release readiness includes governance evidence.
- Story 18: docs claim state remains part of readiness.

**Observable behaviors**

- `agent-harness release readiness` includes governance gates.
- Release readiness verifies governance summary generation.
- Release readiness verifies Markdown/JSON report generation.
- Release readiness verifies governance check behavior.
- Critical governance findings fail release readiness.
- Advisory governance findings remain visible.
- Release readiness links to governance report artifacts.

**First RED test**

- A release-readiness integration test seeds a critical governance violation,
  runs `agent-harness release readiness`, and asserts readiness is not ready,
  governance gates are present, critical finding count is nonzero, advisory
  findings are visible, and report artifact references are safe.

### What to build

Extend release readiness to call or reuse the governance boundary, generate
governance evidence under release evidence or the governance export directory,
evaluate blocking findings, and include report links in the readiness payload.
Do not add compliance mapping or formal attestation.

### Acceptance criteria

- [ ] Release readiness records governance summary evidence.
- [ ] Release readiness records governance report generation evidence.
- [ ] Release readiness records governance check status and exit semantics.
- [ ] Critical governance findings block readiness.
- [ ] Advisory governance findings remain visible without blocking by default.
- [ ] Governance report/index/findings artifact references are safe and
      redaction-safe.
- [ ] Readiness docs identify V12 outputs as inputs to future compliance
      evidence, not compliance readiness.

### Out of scope

- V1.9 Compliance Evidence Pack.
- Formal compliance framework mapping.
- Hosted attestations.
- New release automation.

---

## Cross-Phase Invariants

- Governance never executes runs, providers, templates, MCP tools, or
  orchestration children.
- Governance never mutates runs, approvals, policies, configs, source
  artifacts, templates, skills, or existing evidence.
- Governance export is the only governance write path and writes only to the
  requested governance export directory.
- Policy remains the permission ceiling.
- Optional absent domains report `not_present` unless selected release/profile
  policy requires evidence.
- Enabled or used domains missing required evidence report `missing_evidence`.
- Malformed evidence reports `malformed_evidence` and creates a governance
  finding.
- Raw provider payload contents, secrets, API keys, env var values, raw
  headers, unredacted sensitive context, absolute local paths, and path
  traversal references never enter reports, API responses, exports, or UI
  views.
- Tests verify behavior through public CLI commands, public API routes,
  packaged UI assets, exported artifacts, and release-readiness output.
- Do not introduce hosted governance, multi-user auth, enterprise control
  planes, compliance readiness, cloud deployment, or formal certification
  claims without a separate PRD and release evidence.
