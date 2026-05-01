# PRD: Agent Harness v1.9.0 Compliance Evidence Pack

v1.9.0 targets the Compliance Evidence Pack after the v1.8.0 / V12 Local
Governance Console is complete. The feature packages existing governance and
release evidence into portable, redaction-safe review artifacts.

The pack supports review, audit preparation, security discussion, and future
control mapping. It does not certify legal, regulatory, security, or
organizational compliance.

## Problem Statement

Agent Harness already emits local evidence across runs, policy, approvals,
provider use, retrieval provenance, templates, skills, MCP resources,
orchestration, security findings, docs checks, and release readiness. V12 adds
local governance aggregation over those artifacts. Reviewers still need a
portable way to export the resulting evidence for review outside the local
operator session.

Without a pack boundary, reviewers have to collect governance exports, release
evidence, run artifacts, hashes, findings, and documentation disclaimers by
hand. That manual workflow is slow, inconsistent, and easy to overstate. It is
also risky because raw provider payloads, secrets, private uploads, absolute
machine paths, or other unsafe artifacts could be copied into a review bundle.

The affected actors are:

- release maintainers who need a reproducible evidence bundle before release
- security reviewers who need redaction-safe artifact indexes and findings
- governance reviewers who need evidence mapped to review themes
- operator UI users who need local read-only evidence pack status
- documentation reviewers who need claim boundaries to remain explicit

## Solution

Add an `agent_harness.evidence` boundary that consumes completed V12 governance
outputs and packages them into canonical JSON artifacts, optional Markdown
presentation, deterministic checksums, and an optional archive.

The primary workflow is:

1. Run normal Agent Harness workflows or demos.
2. Generate V12 governance exports under `.agent-harness/governance/`.
3. Run `agent-harness evidence pack --output .agent-harness/evidence/`.
4. Inspect `evidence_pack.v1.json`, `evidence_index.v1.json`,
   `control_mapping.v1.json`, `evidence_findings.v1.json`,
   `evidence_manifest.v1.json`, Markdown reports when requested, and
   `checksums.sha256`.
5. Run `agent-harness evidence check` to validate current evidence state and
   any existing pack files.
6. Run `agent-harness evidence index` to print `evidence_index.v1` JSON.
7. Inspect evidence pack status through read-only local operator routes and UI
   views.
8. Run `agent-harness release readiness`; readiness validates an existing pack
   but does not generate one.

v1.9 packages evidence. It does not rebuild V12 governance aggregation. If the
required V12 governance outputs are unavailable, evidence pack generation fails
with a clear prerequisite error that tells the user to run governance export or
the relevant governance check first.

Required V12 prerequisite artifacts are:

- `governance_summary.v1`
- `governance_report.v1`
- `governance_index.v1`
- `governance_findings.v1`

Every pack must include this disclaimer in JSON and Markdown presentation:

```text
This evidence pack supports review and audit preparation. It does not certify compliance with any legal, regulatory, security, or organizational framework.
```

## User Stories

1. As a release maintainer, I want to export one evidence pack from existing
   governance outputs, so that release review does not require manual artifact
   collection.
2. As a reviewer, I want canonical JSON evidence artifacts, so that downstream
   tooling can consume stable contracts instead of Markdown presentation.
3. As a reviewer, I want optional Markdown reports, so that humans can inspect
   the same evidence without treating Markdown as the source of truth.
4. As a security reviewer, I want unsafe artifacts omitted or redacted, so that
   provider payloads, credentials, private uploads, PII, and absolute local
   paths do not enter the pack.
5. As a governance reviewer, I want a hash-based artifact index, so that every
   included or omitted evidence reference is portable and reviewable.
6. As a governance reviewer, I want lightweight control mapping, so that
   evidence can be reviewed against selected themes without asserting control
   effectiveness or certification.
7. As a release maintainer, I want deterministic pack ids and checksums under a
   fixed timestamp, so that tests and review fixtures can prove repeatability.
8. As a release maintainer, I want archive creation to be opt-in, so that normal
   pack generation does not create extra binary artifacts.
9. As an operator API user, I want token-protected read-only evidence routes,
   so that local tools can inspect evidence pack state without arbitrary file
   reads or mutation.
10. As an operator UI user, I want an Evidence Pack section, so that I can
    inspect overview, control mapping, artifact index, findings, exported
    packs, and release evidence from the local UI.
11. As a release maintainer, I want release readiness to validate an existing
    evidence pack, so that critical evidence findings can block readiness
    without making release readiness mutate the workspace.
12. As a documentation reviewer, I want docs checks to reject unsupported
    implemented claims, so that evidence pack docs do not imply formal
    compliance, certification, or auditor approval.
13. As a reviewer, I want missing optional domains to report `not_present`, so
    that absence is visible without becoming a false blocking failure.
14. As a reviewer, I want malformed or missing required evidence to produce
    clear findings or prerequisite errors, so that pack validity is explainable.
15. As a maintainer, I want the evidence boundary separated from governance,
    release, policy, and operator boundaries, so that each subsystem keeps a
    small public contract.

## Behavioral Requirements

1. `agent-harness evidence pack` writes to `.agent-harness/evidence/` by
   default when no output is supplied.
2. The default pack behavior is equivalent to
   `--output .agent-harness/evidence/ --profile default --format bundle`.
3. `agent-harness evidence pack --output <dir>` writes all generated pack files
   under the selected output directory.
4. `agent-harness evidence pack --profile <name>` records the selected profile
   in the pack contract.
5. `agent-harness evidence pack --format bundle` writes canonical JSON,
   Markdown presentation, and checksums.
6. `agent-harness evidence pack --format json` writes canonical JSON and
   checksums, and omits Markdown.
7. `agent-harness evidence pack --format markdown` writes Markdown plus the
   required canonical JSON artifacts and checksums.
8. `evidence_pack.v1.json` is always written.
9. `evidence_manifest.v1.json` is always written.
10. `evidence_index.v1.json` is always written.
11. `evidence_findings.v1.json` is always written.
12. `control_mapping.v1.json` is always written.
13. `checksums.sha256` is always written.
14. `evidence_pack.v1.md` and `control_mapping.v1.md` are written only for
    formats that include Markdown.
15. `agent-harness evidence pack --archive` creates
    `.agent-harness/evidence/archive/agent-harness-evidence-pack-<timestamp>.zip`.
16. No archive is created unless `--archive` is supplied.
17. `checksums.sha256` excludes itself, uses normalized relative paths, hashes
    only exported evidence files, and sorts lines deterministically.
18. The pack builder reads only known artifact roots and V12 governance export
    files through existing boundaries.
19. The pack builder does not scan arbitrary workspace files.
20. The pack builder does not rebuild governance aggregation.
21. Missing required V12 governance outputs fail pack generation with a
    prerequisite error and exit code `2`.
22. Malformed required V12 governance outputs fail clearly or create blocking
    evidence findings, depending on whether a safe partial pack can be built.
23. `agent-harness evidence check` builds evidence state in memory and
    validates existing pack files when present.
24. `agent-harness evidence check` exits `0` when evidence is valid and no
    blocking evidence findings exist.
25. `agent-harness evidence check` exits `1` when blocking evidence findings
    exist.
26. `agent-harness evidence check` exits `2` for invalid input, config,
    artifact root, or missing prerequisite artifacts.
27. `agent-harness evidence check` exits `3` for internal errors.
28. `agent-harness evidence index` prints `evidence_index.v1` JSON.
29. `pack_id` is deterministic from Agent Harness version, selected profile,
    normalized workspace identity, governance input hashes, and generation
    timestamp.
30. Tests can use a fixed generation timestamp to prove deterministic pack ids
    and checksums.
31. If a public deterministic timestamp flag is added, it is limited to
    `--generated-at 2026-01-01T00:00:00Z`; otherwise fixed timestamp behavior
    stays internal to tests.
32. Artifact references in pack outputs are project-relative, normalized,
    allowlisted, hash-indexed, and schema-versioned where applicable.
33. Absolute paths, path traversal references, raw provider payload references,
    raw vector DB internals, private upload references, and credential
    references are rejected or omitted with safe findings.
34. Raw provider payloads, credentials, API keys, environment variable values,
    raw headers, private uploaded files, PII, customer data, secret values,
    absolute local paths, and raw vector DB internals never appear in pack
    contents.
35. Unsafe artifacts are represented by safe metadata, content hash where safe,
    redaction status, and omission reason.
36. Optional domains absent from available evidence report `not_present` unless
    selected release policy makes them required.
37. Control mappings use review themes such as AI risk governance, secure
    software development, data classification, provider governance, approval
    governance, retrieval provenance, supply-chain evidence, documentation
    claim control, and release readiness.
38. Control mapping wording is limited to evidence being mapped for review
    against selected control themes.
39. Control mapping does not assert control effectiveness, certification,
    audit pass/fail status, legal compliance, or readiness for formal
    frameworks.
40. The local operator API exposes token-protected read-only routes for
    evidence overview, packs, pack detail, control map, artifact index, and
    findings.
41. Operator evidence routes are local-only, artifact-backed, redaction-safe,
    and do not perform arbitrary filesystem reads.
42. Operator evidence routes do not expose raw provider payloads, secrets, or
    unredacted sensitive content.
43. Operator evidence routes do not mutate runs, approvals, policies, configs,
    governance exports, evidence packs, or release evidence.
44. The local operator UI includes an Evidence Pack section with Overview,
    Control Mapping, Artifact Index, Findings, Exported Packs, and Release
    Evidence views.
45. The UI does not imply formal compliance, certification, or auditor
    approval.
46. `agent-harness release readiness` validates an existing evidence pack under
    `.agent-harness/evidence/`.
47. Release readiness does not generate evidence packs.
48. Release readiness treats a missing evidence pack as a prerequisite error.
49. Critical evidence findings block release readiness.
50. Advisory evidence findings remain visible without blocking by default.
51. Release readiness links only safe evidence pack artifacts.
52. Documentation checks reject unsupported implemented claims for
    compliance-ready scope, SOC2-ready scope, ISO-ready scope,
    GDPR-compliant scope, enterprise-certified scope, regulatory compliant
    scope, auditor-approved scope, NIST compliant scope, and OWASP compliant
    scope unless the wording is clearly a forbidden phrase, roadmap item, or
    disclaimer.

## Implementation Decisions

- Add `agent_harness.evidence` as the v1.9 boundary. It owns prerequisite
  validation, pack construction, artifact indexing, redaction-safe packaging,
  control mapping, check semantics, checksum generation, archive creation, and
  evidence API payload construction.
- Keep V12 governance aggregation in `agent_harness.governance`. The evidence
  boundary consumes V12 outputs instead of recreating domain aggregation.
- Add evidence contracts with `StrictModel` for `evidence_pack.v1`,
  `evidence_index.v1`, `control_mapping.v1`, `evidence_findings.v1`,
  `evidence_manifest.v1`, and an export result contract.
- Treat JSON as the canonical contract. Markdown is presentation generated from
  canonical evidence data.
- Store default evidence pack files under `.agent-harness/evidence/`.
- Store archives only under `.agent-harness/evidence/archive/` and only when
  requested.
- Reuse existing utilities for stable ids, UTC timestamps, JSON writing, path
  normalization, content hashing, and schema validation where they fit the
  public behavior.
- Reuse existing config, policy, governance, storage, release, operator,
  docs-check, template, skill, MCP, orchestration, security, and advisory
  boundaries through public contracts or known artifact roots.
- Keep provider payload handling metadata-only unless a redacted evidence
  artifact is explicitly safe.
- Keep release readiness non-mutating. It validates existing pack files and
  records safe links and findings.
- Extend the existing local operator app. Do not create a second server or
  hosted evidence service.
- Extend the packaged vanilla operator UI. Do not introduce a frontend build
  toolchain, remote assets, analytics, or browser persistence for evidence
  state.
- Keep external scanners and SBOM generation optional. Reference their
  artifacts when present; report `not_present` when absent unless a selected
  release policy requires them.
- Add documentation for the evidence pack and update public capability docs
  only when the behavior is implemented and tested.

## Testing Decisions

- Test evidence behavior through public CLI commands, exported pack artifacts,
  public operator API routes, packaged UI assets, and release-readiness output.
- Unit tests should cover schema validation, pack id determinism, checksum
  sorting, safe relative path validation, hash generation, control mapping,
  disclaimer presence, finding severity mapping, redaction classification, and
  export result contracts.
- Integration tests should cover pack generation from fixture V12 governance
  data, bundle output, JSON-only output, Markdown output, artifact index
  printing, evidence check pass/fail paths, archive opt-in behavior, operator
  API evidence routes, UI smoke behavior, and release-readiness integration.
- Adversarial tests should cover raw provider payload omission, environment
  value redaction, absolute path rejection, path traversal rejection, private
  upload reference rejection, PII-like fixture omission or redaction,
  unsupported documentation claim detection, malformed governance input,
  missing required governance evidence, and raw vector DB internals omission.
- Tests should verify behavior through public contracts and stable artifacts,
  not private helper names.
- Tests may assert deterministic ordering where the output contract requires
  deterministic files, checksums, or indexes.
- V0 acceptance is the ability to fail clearly when V12 prerequisites are
  absent and to generate a minimal canonical pack from fixture V12 outputs.
- Full v1.9 acceptance requires CLI pack/check/index, redaction-safe JSON and
  Markdown artifacts, checksums, control mapping, operator API/UI visibility,
  release-readiness validation, docs claim guards, and explicit
  non-certification disclaimers.

## Out of Scope

- Implementing v1.9 in this planning task.
- Rebuilding V12 governance aggregation inside `agent_harness.evidence`.
- Generating V12 governance outputs as a side effect of evidence pack
  generation.
- Creating evidence packs as a side effect of release readiness.
- Claiming SOC2, ISO, GDPR, NIST, OWASP, legal, regulatory, auditor-approved,
  enterprise-certified, or formal organizational compliance.
- Asserting control effectiveness or audit pass/fail status.
- Hosted evidence APIs, hosted dashboards, cloud storage, remote review
  portals, multi-tenant evidence services, or organization-wide control
  planes.
- Multi-user identity, external auditor workflows, signatures, attestations,
  or signed evidence bundles.
- Mandatory external scanners, mandatory SBOM tooling, or network dependency
  checks in the default local pack path.
- Arbitrary filesystem browsing or workspace scanning.
- Copying unsafe raw artifacts directly into the evidence pack.
- Exposing raw provider payloads, raw headers, credentials, API keys,
  environment values, private uploads, PII, customer data, raw vector DB
  internals, or absolute local machine paths.
- Changing policy decisions, approval behavior, provider behavior, retrieval
  behavior, governance findings, or release automation based on evidence pack
  generation.

## Further Notes

The central architectural risk is duplication. v1.9 must package V12
governance evidence rather than becoming a second governance aggregator.

The central safety risk is disclosure. The pack is portable, so every artifact
reference, index entry, Markdown line, API payload, and checksum path has to be
safe outside the local machine context.

The central product risk is overclaiming. Control mapping should help humans
review evidence against selected themes, but every public surface must preserve
the non-certification disclaimer and avoid implying formal compliance.

The current roadmap marks V12 as in progress with governance summary, check,
report, and export implemented through Phase 3 while operator API/UI and
release-readiness governance gates remain future-only. v1.9 implementation
should either start only after V12 is completed or make its prerequisite
failure path the first tested behavior.
