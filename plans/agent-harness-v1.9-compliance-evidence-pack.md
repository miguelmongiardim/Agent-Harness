# Plan: Agent Harness v1.9.0 Compliance Evidence Pack

> Source PRD:
> [docs/prd-agent-harness-v1.9-compliance-evidence-pack.md](../docs/prd-agent-harness-v1.9-compliance-evidence-pack.md)

This plan follows the PRD -> Plan -> TDD workflow. It is intentionally limited
to planning; do not implement these phases until a separate implementation
request starts TDD execution.

v1.9.0 depends on completed v1.8.0 / V12 governance exports. The evidence
boundary packages governance evidence into portable review artifacts. It does
not rebuild governance aggregation or claim formal compliance.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness evidence pack`, `check`, and
  `index`. `pack` supports `--output`, `--profile`, `--format
  bundle|json|markdown`, and opt-in `--archive`.
- **Key models**: add evidence pack, evidence manifest, evidence index,
  evidence finding, control mapping, export result, prerequisite error, and
  checksum contracts under the evidence boundary.
- **Schema**: introduce `evidence_pack.v1`, `evidence_manifest.v1`,
  `evidence_index.v1`, `evidence_findings.v1`, `control_mapping.v1`, and an
  evidence export result contract using `StrictModel`.
- **Storage**: default writes go under `.agent-harness/evidence/`; archives go
  under `.agent-harness/evidence/archive/` only when requested. The pack reads
  completed V12 exports under `.agent-harness/governance/` and known artifact
  roots only.
- **Runtime boundary**: evidence packaging is non-executing. It does not run
  tasks, providers, retrieval, scanners, governance aggregation, templates, MCP
  servers, orchestration children, or release automation.
- **Policy boundary**: policy remains the permission ceiling. Evidence can
  report policy state, findings, and omissions, but cannot widen permissions or
  alter policy.
- **Approval model**: approval evidence is packaged and checked. Approval
  mutation remains in existing approval flows.
- **Audit model**: all pack references are project-relative, normalized,
  allowlisted, hash-indexed, schema-versioned where applicable, and tagged with
  redaction status and omission reason.
- **Operator boundary**: extend the existing loopback-only operator app with
  token-protected read-only evidence routes and packaged static UI views.
- **Release boundary**: release readiness validates an existing pack and links
  safe artifacts. It does not generate evidence packs.
- **External service boundary**: the default evidence workflow is local-only.
  SBOM and scanner artifacts are referenced when present and otherwise reported
  as `not_present` unless a selected release policy requires them.
- **Claim boundary**: every pack includes the non-certification disclaimer. No
  CLI, API, UI, doc, or Markdown output asserts legal, regulatory, security, or
  organizational certification.

---

## Phase 0: Scope Docs And Claim Guard

**User stories covered**

- Story 12: documentation reviewer can reject unsupported implemented claims.
- Story 15: maintainer keeps evidence packaging separate from governance,
  release, policy, and operator boundaries.

**Observable behaviors**

- v1.9 PRD and implementation plan exist as durable planning artifacts.
- Public docs can describe v1.9 as planned or implemented only within the
  actual behavior delivered by tests.
- Docs checks reject unsupported implemented claims for formal compliance,
  certification, auditor approval, and framework compliance wording.

**First RED test**

- Add a docs-check integration test that fails when implemented-scope docs say
  the evidence pack is compliance-ready, SOC2-ready, ISO-ready,
  GDPR-compliant, enterprise-certified, regulatory compliant, auditor-approved,
  NIST compliant, or OWASP compliant outside forbidden-wording, roadmap, or
  disclaimer context.

### What to build

Add or update the v1.9 PRD, vertical plan, evidence pack docs, roadmap links,
and claim scanner rules. Keep this phase documentation and claim-boundary only.
Do not add evidence CLI, schemas, pack writing, operator routes, UI, or release
readiness behavior.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v1.9-compliance-evidence-pack.md` exists.
- [x] `plans/agent-harness-v1.9-compliance-evidence-pack.md` exists.
- [x] `docs/compliance-evidence-pack.md` describes implemented behavior only
      after the behavior exists.
- [x] README, roadmap, release-readiness, operator, architecture, and security
      docs distinguish implemented evidence packaging from future formal
      compliance work.
- [x] Docs checks reject unsupported implemented compliance or certification
      claims.
- [x] V12 governance prerequisite is documented.

### Phase 0 implementation notes

- Added `unsupported_evidence_pack_claim` docs-check coverage for
  compliance-ready, SOC2-ready, ISO-ready, GDPR-compliant,
  enterprise-certified, regulatory compliant, auditor-approved, NIST compliant,
  and OWASP compliant evidence-pack claims outside roadmap, denial, or
  disclaimer context.
- Added `docs/compliance-evidence-pack.md` with the planned V1.9 boundary,
  required V12 prerequisite artifacts, non-certification disclaimer, and unsafe
  artifact exclusions.
- Updated README, roadmap, release-readiness, operator, architecture, and
  security docs to keep V1.9 planned, V12-dependent, local-only, and
  non-certifying.
- Scope stayed Phase 0-only: no evidence CLI, schema, pack writing, operator
  route, UI, or release-readiness behavior was added.

### Out of scope

- Evidence pack generation.
- Evidence schemas.
- Operator evidence routes or UI.
- Release readiness evidence gates.

---

## Phase 1: Missing V12 Governance Fails Clearly

**User stories covered**

- Story 1: release maintainer exports from existing governance outputs.
- Story 14: malformed or missing required evidence produces clear failures.
- Story 15: evidence does not rebuild governance aggregation.

**Observable behaviors**

- `agent-harness evidence pack` fails with exit code `2` when required V12
  exports are absent.
- The failure names the missing prerequisite class without exposing absolute
  local paths or raw artifact content.
- The error tells the user to generate V12 governance exports first.
- `agent-harness evidence check` returns exit code `2` for the same missing
  prerequisite state.

**First RED test**

- In a seeded project without `.agent-harness/governance/` exports, run
  `agent-harness evidence pack --output .agent-harness/evidence/` and assert
  exit code `2`, no evidence pack files, a redaction-safe prerequisite message,
  and no governance aggregation side effects.

### What to build

Create the narrowest evidence boundary and CLI wiring needed to load config,
resolve the governance export directory, validate the four required V12
contracts, and fail safely. This phase proves the prerequisite contract before
any pack output exists.

### Acceptance criteria

- [x] `agent-harness evidence --help` exposes `pack`, `check`, and `index`.
- [x] Missing `governance_summary.v1` fails with a prerequisite error.
- [x] Missing `governance_report.v1` fails with a prerequisite error.
- [x] Missing `governance_index.v1` fails with a prerequisite error.
- [x] Missing `governance_findings.v1` fails with a prerequisite error.
- [x] Failure output uses project-relative references or artifact class names
      only.
- [x] No V12 governance files are generated by evidence commands.

### Phase 1 implementation notes

- Added the `agent_harness.evidence` boundary with an `evidence_check.v1`
  result contract for prerequisite validation.
- Added `agent-harness evidence pack`, `check`, and `index` CLI wiring.
- `pack` and `check` validate the four required V12 governance export files
  under `.agent-harness/governance/` and return exit code `2` with
  redaction-safe diagnostics when exports are absent.
- Scope stayed Phase 1-only: no successful pack generation, checksums, control
  mapping, operator routes, UI, or release-readiness evidence gates.

### Out of scope

- Successful pack generation.
- Control mapping.
- Checksums.
- Operator routes.
- Release readiness gates.

---

## Phase 2: Minimal Canonical Pack From V12 Exports

**User stories covered**

- Story 1: release maintainer can export one evidence pack.
- Story 2: reviewer gets canonical JSON artifacts.
- Story 7: deterministic ids are testable under fixed time.

**Observable behaviors**

- Given fixture V12 governance exports, `agent-harness evidence pack` writes
  canonical JSON artifacts and `checksums.sha256`.
- The generated pack records profile, workspace identity, Agent Harness
  version, governance references, release-readiness reference when present,
  redaction status, claim status, and the required disclaimer.
- Pack ids and checksums are deterministic under a fixed timestamp fixture.

**First RED test**

- Seed fixture `governance_summary.v1`, `governance_report.v1`,
  `governance_index.v1`, and `governance_findings.v1`; set a fixed generation
  timestamp; run `evidence pack`; assert the five required JSON/checksum files,
  schema versions, disclaimer, deterministic `pack_id`, deterministic checksum
  lines, and no Markdown files for `--format json`.

### What to build

Build the first successful end-to-end pack path from V12 exports to canonical
JSON artifacts. Introduce only the models and rendering needed by this path:
pack summary, manifest, findings export, index pass-through/normalization, and
export result.

### Acceptance criteria

- [x] `evidence_pack.v1.json` is generated.
- [x] `evidence_manifest.v1.json` is generated.
- [x] `evidence_index.v1.json` is generated.
- [x] `evidence_findings.v1.json` is generated.
- [x] `checksums.sha256` is generated.
- [x] JSON artifacts validate with `StrictModel`.
- [x] Pack id is deterministic under fixed generation time.
- [x] Checksum lines are deterministic and exclude `checksums.sha256`.
- [x] The non-certification disclaimer appears in `evidence_pack.v1.json`.

### Phase 2 implementation notes

- Added `evidence_pack.v1`, `evidence_manifest.v1`, `evidence_index.v1`,
  `evidence_findings.v1`, and `evidence_export_result.v1` contracts under the
  evidence boundary.
- Added `agent-harness evidence pack --format json` generation from existing
  V12 governance exports into canonical JSON files and deterministic
  `checksums.sha256`.
- Pack ids use the fixed generation time hook in tests and the selected
  profile, Agent Harness version, workspace identity, governance references,
  and governance input hashes.
- Scope stayed Phase 2-only: no Markdown presentation, archive creation, full
  control mapping, operator routes, UI, release-readiness gate, governance
  aggregation, workflow execution, provider calls, scanners, or arbitrary
  workspace scanning were added.

### Out of scope

- Markdown presentation.
- Archive creation.
- Full control mapping.
- Operator API/UI.
- Release readiness integration.

---

## Phase 3: Redaction-Safe Artifact Index

**User stories covered**

- Story 4: security reviewer gets unsafe artifact omission.
- Story 5: governance reviewer gets a portable hash-based index.
- Story 13: absent optional domains are represented without false failure.

**Observable behaviors**

- Evidence index entries are safe relative references with hashes where safe.
- Raw provider payloads, credentials, absolute paths, path traversal refs,
  private upload refs, PII-like fixture content, and raw vector DB internals are
  excluded or redacted.
- Unsafe artifacts create findings with omission reasons and never appear as
  copied pack content.
- Optional absent domains report `not_present` unless required by selected
  release policy.

**First RED test**

- Seed a V12 governance index that references a safe run summary, an absolute
  local path, a path traversal ref, a raw provider payload, and a private upload
  marker. Run `evidence pack` and assert safe inclusion for the run summary,
  exclusion findings for unsafe refs, no leaked content, and no absolute
  machine path in any output.

### What to build

Add artifact-reference normalization, allowlisting, redaction classification,
omission reason handling, safe content hashing, and evidence findings for
unsafe or malformed references. Keep the pack builder metadata-first; do not
copy source artifacts into the pack.

### Acceptance criteria

- [x] Included artifact refs are project-relative and normalized.
- [x] Path traversal refs are rejected.
- [x] Absolute local paths are rejected.
- [x] Raw provider payload refs are excluded with findings.
- [x] Private upload refs are excluded with findings.
- [x] Credential/env-var-like values never appear in pack files.
- [x] Unsafe raw vector DB internals are excluded.
- [x] Optional absent domains are represented as `not_present`.
- [x] Findings include severity, domain, recommendation,
      `blocks_release`, and `blocks_evidence_pack`.

### Phase 3 implementation notes

- Extended `evidence pack --format json` to consume `governance_index.v1`
  entries as metadata-only source references.
- Included safe artifact refs are normalized project-relative paths with
  content hashes recomputed from local files, not trusted from governance input.
- Absolute paths, traversal refs, raw provider payloads, private upload refs,
  credential-like refs, and raw vector database internals are omitted and
  represented as `evidence_finding.v1` records with omission reasons.
- `evidence_pack.v1` now records known evidence domains and reports absent
  optional domains as `not_present`.
- Scope stayed Phase 3-only: no Markdown presentation, archive creation,
  control mapping, operator routes, UI, release-readiness gate, governance
  aggregation, scanner execution, or copied raw artifacts were added.

### Out of scope

- Control mapping presentation.
- Operator UI.
- Release readiness gates.

---

## Phase 4: Review-Only Control Mapping

**User stories covered**

- Story 6: reviewer gets lightweight control mapping without effectiveness
  claims.
- Story 12: docs and outputs avoid unsupported compliance claims.

**Observable behaviors**

- `control_mapping.v1.json` maps available evidence refs to internal review
  themes.
- Markdown control mapping includes the non-certification disclaimer when
  Markdown output is requested.
- Uncovered review themes report `not_covered`, `partially_covered`,
  `not_applicable`, or `roadmap_only` rather than pass/fail certification.
- Forbidden compliance and framework wording does not appear as an implemented
  claim.

**First RED test**

- Run `evidence pack --format bundle` against fixture governance exports and
  assert `control_mapping.v1.json`, `control_mapping.v1.md`, evidence refs for
  covered themes, `not_covered` for missing themes, disclaimer text, and absence
  of framework-compliant or certification claims.

### What to build

Add internal control theme definitions and a deterministic mapper from safe
evidence index/domain data to control mapping records. Treat NIST, OWASP, and
similar references only as inspiration or selected review framing, never as
assertions of compliance.

### Acceptance criteria

- [x] `control_mapping.v1.json` is generated.
- [x] `control_mapping.v1.md` is generated for Markdown-including formats.
- [x] Coverage statuses are limited to `covered`, `partially_covered`,
      `not_covered`, `not_applicable`, and `roadmap_only`.
- [x] Control mappings reference safe evidence refs only.
- [x] Mapping output includes limitations.
- [x] Mapping output includes the non-certification disclaimer.
- [x] Docs check covers forbidden implemented wording for compliance and
      framework claims.

### Phase 4 implementation notes

- Added `control_mapping.v1` contracts with deterministic review-theme entries,
  limited coverage statuses, source domains, safe evidence refs, limitations,
  and the non-certification disclaimer.
- `agent-harness evidence pack` now writes `control_mapping.v1.json` as part
  of the canonical JSON artifact set.
- Bundle output also writes `control_mapping.v1.md` as review-only Markdown
  presentation generated from the canonical mapping.
- Mappings are derived from packaged domain summaries and included safe
  evidence refs; unsafe governance-index refs remain omitted through Phase 3
  findings instead of appearing in mapping output.
- Scope stayed Phase 4-only: no full Markdown pack presentation, archive
  creation, operator routes, UI views, release-readiness gate, framework
  certification, auditor workflow, signed attestation, or policy change was
  added.

### Out of scope

- External framework certification.
- Auditor workflow.
- Signed attestations.
- Policy changes based on control mapping.

---

## Phase 5: Pack Formats, Archive, Check, And Index Commands

**User stories covered**

- Story 3: reviewer gets optional Markdown presentation.
- Story 8: archive creation is opt-in.
- Story 14: check results explain blocking and prerequisite states.

**Observable behaviors**

- `--format bundle`, `--format json`, and `--format markdown` produce the
  documented file sets.
- `--archive` creates a zip under `archive/`; no archive exists by default.
- `evidence check` validates in-memory state and existing pack files when
  present.
- `evidence index` prints `evidence_index.v1` JSON.

**First RED test**

- Run pack generation three times against the same fixture governance exports
  with `bundle`, `json`, and `markdown`; assert exact file sets, archive opt-in
  behavior, check exit codes, and `index` JSON output matching the generated
  index contract.

### What to build

Complete the CLI behavior around the pack builder: Markdown rendering,
format-specific file selection, checksum regeneration, archive writing,
existing-pack validation, check exit code mapping, and index printing.

### Acceptance criteria

- [x] `--format bundle` writes JSON, Markdown, and checksums.
- [x] `--format json` writes JSON and checksums, and omits Markdown.
- [x] `--format markdown` writes Markdown plus canonical JSON and checksums.
- [x] `--archive` creates the documented zip path.
- [x] No archive is created without `--archive`.
- [x] `evidence check` returns exit codes `0`, `1`, `2`, and `3` for the
      documented conditions.
- [x] `evidence index` prints valid `evidence_index.v1` JSON.

### Phase 5 implementation notes

- Added `evidence_pack.v1.md` presentation for Markdown-including formats
  while keeping JSON artifacts canonical.
- `--format json` writes canonical JSON plus checksums only; `--format
  bundle` and `--format markdown` write canonical JSON, Markdown presentation,
  and checksums.
- Added `agent-harness evidence pack --archive`, which creates an opt-in zip
  under the selected evidence output directory's `archive/` folder and leaves
  archives out of `checksums.sha256`.
- Split prerequisite validation from full evidence checks so `pack` and
  `index` can still package safe metadata and findings, while `check` returns
  `0` for valid state, `1` for blocking evidence findings, `2` for invalid
  input or missing prerequisites, and `3` for internal check errors.
- `evidence check` validates both current in-memory pack state and existing
  `evidence_findings.v1.json` pack findings when present.
- `agent-harness evidence index` now prints valid current `evidence_index.v1`
  JSON through the same in-memory evidence state used by pack and check.
- Scope stayed Phase 5-only: no operator API/UI route, release-readiness gate,
  mandatory scanner execution, governance aggregation rebuild, provider call,
  workflow run, or arbitrary workspace scan was added.

### Out of scope

- Operator API/UI.
- Release readiness gates.
- Mandatory external scanner execution.

---

## Phase 6: Evidence Domains Are Packaged From Governance Outputs

**User stories covered**

- Story 4: unsafe evidence remains omitted or redacted.
- Story 5: artifact index covers included and excluded domains.
- Story 13: optional missing domains are explicit.

**Observable behaviors**

- Pack summaries cover governance, policy, approval, provider, retrieval,
  template, skill, MCP, multi-agent, supply-chain, security, docs claim, and
  release-readiness domains as represented by V12 governance outputs and safe
  referenced artifacts.
- Present domains include safe summaries and refs.
- Absent optional domains report `not_present`.
- Malformed domain evidence produces findings without crashing safe pack
  generation.

**First RED test**

- Seed fixture governance exports with representative domain statuses and safe
  evidence refs for policy, approvals, provider, retrieval, templates, skills,
  MCP, orchestration, supply-chain/advisory, docs, and release readiness. Run
  `evidence pack` and assert domain summaries, omitted optional domains,
  findings for malformed evidence, and safe index coverage.

### What to build

Expand the evidence pack domain summary and manifest construction using V12
governance outputs as the source of aggregation. Read extra source artifacts
only when they are known, allowlisted, and needed to package safe metadata.

### Acceptance criteria

- [x] Governance evidence refs point to V12 governance outputs.
- [x] Policy evidence answers what controls execution, what can widen
      permissions, and what is denied by default.
- [x] Approval evidence answers whether risky actions were reviewed and bound
      to proposed effects.
- [x] Provider evidence includes safe profile, trust-zone, approval-linkage,
      redaction, sensitivity, and metadata summaries.
- [x] Retrieval evidence includes safe provenance, backend, local-first, and
      rejection summaries.
- [x] Template and skill evidence includes validation, inventory, and local
      guidance summaries.
- [x] MCP and multi-agent domains report present safe summaries or
      `not_present`.
- [x] Supply-chain evidence references optional SBOM/scanner/license artifacts
      when present and reports `not_present` when absent.
- [x] Docs claim evidence records unsupported-claim scanner results.

### Out of scope

- Recomputing V12 governance aggregation.
- Running scanners or SBOM generation as part of pack generation.
- Creating new provider, retrieval, template, skill, MCP, or orchestration
  evidence.

### Phase 6 implementation notes

- Added safe `summary` payloads to `evidence_pack.v1` domain summaries, sourced
  from `governance_summary.v1` rather than recomputed by evidence packaging.
- Packaged safe summaries and refs for governance, policy, approvals, provider,
  retrieval, templates, skills, MCP, multi-agent, supply-chain, security, docs
  claim, and release-readiness domains when V12 reports them.
- Kept absent optional domains as `not_present` with empty summaries.
- Malformed domain summary payloads now become `malformed_domain_summary`
  evidence findings and set the affected domain to `malformed_evidence`
  without crashing pack generation.

---

## Phase 7: Operator API Exposes Evidence Pack State

**User stories covered**

- Story 9: local tools can inspect evidence through token-protected routes.
- Story 4: API responses are redaction-safe.

**Observable behaviors**

- The existing operator app exposes read-only `/api/v1/evidence/*` routes.
- All evidence routes require `X-Agent-Harness-Operator-Token`.
- Routes return artifact-backed evidence overview, pack list, pack detail,
  control map, artifact index, and findings.
- Routes reject arbitrary filesystem reads and unsupported mutation methods.

**First RED test**

- Create a fixture evidence pack, start the operator app through test client,
  call each evidence route with no token, wrong token, and valid token, then
  assert token enforcement, schema versions, safe payloads, and no leaked raw
  provider payload or absolute path.

### What to build

Wire the evidence boundary into the existing operator app as token-protected
read-only routes. Reuse pack validation and safe artifact readers rather than
serving arbitrary files.

### Acceptance criteria

- [x] `/api/v1/evidence/overview` returns safe overview data.
- [x] `/api/v1/evidence/packs` lists exported packs from the evidence root.
- [x] `/api/v1/evidence/packs/{pack_id}` returns safe pack detail.
- [x] `/api/v1/evidence/control-map` returns control mapping.
- [x] `/api/v1/evidence/artifact-index` returns the evidence index.
- [x] `/api/v1/evidence/findings` returns evidence findings.
- [x] All routes require the operator token.
- [x] Routes are read-only and artifact-backed.
- [x] Routes do not expose raw provider payloads, secrets, or absolute paths.

### Out of scope

- Operator UI views.
- Pack generation through the API.
- Hosted API behavior.
- Evidence mutation routes.

### Phase 7 implementation notes

- Added token-protected read-only operator evidence routes for overview, pack
  listing, pack detail, control mapping, artifact index, and findings.
- Routes read only fixed evidence artifact filenames under the configured
  `.agent-harness/evidence` root and do not build packs, run governance,
  mutate evidence, or browse arbitrary workspace paths.
- Unsupported mutation methods under `/api/v1/evidence/*` return a read-only
  API error.
- API tests generate a real CLI evidence pack first, then verify token
  enforcement, schema versions, artifact-backed payloads, and redaction safety
  for raw provider payload contents, secrets, and absolute paths.

---

## Phase 8: Operator UI Shows Evidence Pack Views

**User stories covered**

- Story 10: operator UI user can inspect evidence pack views locally.
- Story 12: UI avoids compliance or certification implication.

**Observable behaviors**

- The packaged operator UI has an Evidence Pack section.
- UI views load only local `/api/v1/evidence/*` routes.
- Overview, Control Mapping, Artifact Index, Findings, Exported Packs, and
  Release Evidence views render safe data.
- The UI does not include remote assets, analytics, external API calls, or
  mutation controls for evidence.

**First RED test**

- An operator UI smoke test reads packaged HTML/JS/CSS, asserts Evidence Pack
  navigation and route usage, asserts no external asset markers, asserts no
  evidence mutation requests, and checks that visible labels avoid formal
  compliance or certification wording.

### What to build

Extend the existing vanilla operator UI with read-only evidence views backed by
the evidence API. Keep the display utilitarian and aligned with the current
operator surface.

### Acceptance criteria

- [ ] Evidence Pack section is visible in the local UI.
- [ ] UI fetches only local evidence API routes.
- [ ] UI renders overview, mapping, index, findings, packs, and release
      evidence states.
- [ ] UI handles missing pack and blocking finding states.
- [ ] UI contains no external assets, CDN references, analytics, or browser
      persistence for evidence state.
- [ ] UI contains no evidence mutation controls.
- [ ] UI wording does not imply certification or formal compliance.

### Out of scope

- Generating packs from the UI.
- Rich dashboard frameworks.
- Browser persistence.
- Hosted UI behavior.

---

## Phase 9: Release Readiness Validates Existing Evidence Pack

**User stories covered**

- Story 11: release readiness validates existing pack without mutation.
- Story 14: missing or invalid pack state is explainable.

**Observable behaviors**

- `agent-harness release readiness` includes an evidence pack gate.
- The gate validates an existing pack under `.agent-harness/evidence/`.
- The gate uses evidence check semantics and blocks on critical evidence
  findings.
- Missing pack reports a prerequisite error.
- Release readiness links safe evidence artifacts only.

**First RED test**

- Seed a project with no evidence pack and run release readiness; assert a
  pending readiness result with an evidence-pack prerequisite diagnostic and no
  generated pack files. Then seed a valid pack and a critical evidence finding
  fixture; assert safe links, advisory visibility, and blocking behavior.

### What to build

Integrate evidence check results into release readiness as a non-mutating gate.
Record safe artifact links and finding counts. Do not call pack generation from
release readiness.

### Acceptance criteria

- [ ] Release readiness includes an `evidence_pack` gate.
- [ ] Release readiness does not generate evidence packs.
- [ ] Missing pack reports a prerequisite error.
- [ ] Existing pack files are validated.
- [ ] Critical evidence findings block readiness.
- [ ] Advisory evidence findings remain visible.
- [ ] Safe evidence pack artifacts are linked.
- [ ] Unsafe evidence contents are never exposed in readiness output.

### Out of scope

- Release automation.
- Pack generation from readiness.
- Compliance attestation.
- External auditor workflows.

---

## Cross-Phase Invariants

- Evidence packaging never rebuilds V12 governance aggregation.
- Evidence commands never run tasks, providers, retrieval, scanners, templates,
  MCP tools, orchestration children, or release automation.
- Release readiness validates existing packs and never generates packs.
- JSON artifacts are canonical; Markdown is presentation.
- Every pack includes the non-certification disclaimer.
- Artifact refs are project-relative, normalized, allowlisted, hash-indexed,
  schema-versioned where applicable, and tagged with redaction status.
- Unsafe artifacts are omitted or redacted with findings and omission reasons.
- Raw provider payloads, credentials, API keys, environment values, raw
  headers, private uploads, PII, customer data, secret values, absolute local
  machine paths, raw vector DB internals, and arbitrary workspace files never
  enter pack outputs, API responses, UI views, or readiness output.
- Optional absent domains report `not_present` unless selected release policy
  requires them.
- Control mapping is review framing only and never asserts control
  effectiveness, certification, audit pass/fail status, legal compliance,
  regulatory approval, or formal framework compliance.
- Tests verify behavior through public CLI commands, exported artifacts,
  operator API routes, packaged UI assets, and release-readiness output.
- No subsystem is considered implemented until at least one observable behavior
  test exercises it through a public interface.
