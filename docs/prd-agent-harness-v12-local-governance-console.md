# PRD: Agent Harness V12 Local Governance Console

V12 targets `v1.8.0` after the V11 orchestration and benchmark evidence
tracks. It introduces a local governance evidence surface that aggregates
existing Agent Harness artifacts without turning the project into a hosted
admin platform, enterprise control plane, or compliance product.

## Problem Statement

Agent Harness now records substantial local evidence across policy, runs,
approvals, provider calls, retrieval, templates, skills, MCP resources,
orchestration, security findings, benchmark comparisons, and release
readiness. That evidence is intentionally local and artifact-backed, but it is
spread across several command families and storage locations.

Today a reviewer can inspect individual runs or release gates, but answering a
governance question requires reconstructing state manually. A release
maintainer may need to know which policy profile applied, whether provider
payloads were redacted, which approvals were pending or denied, whether MCP
remained read-only, whether orchestration handoffs were policy-mediated, and
whether release readiness should be blocked. Those questions cut across
boundaries that are currently inspectable only one artifact at a time.

That creates four problems.

First, governance review is inefficient. A reviewer has to know where each
kind of evidence lives and which command exposes it.

Second, absent evidence is ambiguous. A domain may be unused, not implemented
in a project, enabled but missing evidence, malformed, or blocked by policy;
those states should not collapse into one generic missing-file condition.

Third, safety review is fragmented. Raw provider payloads, unsafe artifact
references, path traversal attempts, hard-denied provider-input classes, and
unsupported documentation claims should be surfaced consistently.

Fourth, the future compliance evidence pack needs a stable local evidence
foundation, but V12 must not claim compliance readiness before formal mappings,
controls, and review procedures exist.

The affected actors are:

- reviewers who need a local evidence browser for policy and audit state
- release maintainers who need governance checks to block critical release
  risks
- security reviewers who need proof that reports do not expose secrets or raw
  provider payloads
- policy authors who need to see what was allowed, denied, or approval-gated
- maintainers who need documentation claims to remain aligned with implemented
  behavior

## Solution

V12 adds an `agent_harness.governance` boundary that summarizes, indexes,
checks, reports, and exports existing local evidence. The boundary is
read-only by default. It reads known artifact classes, classifies domain
status, normalizes governance findings, and writes governance exports only when
the user explicitly asks for export.

The user-facing workflow is:

1. Run a local demo or normal Agent Harness workflow.
2. Run `agent-harness governance summary` to inspect governance health at a
   glance.
3. Run `agent-harness governance report --format markdown` or
   `--format json` to produce reviewable reports.
4. Run `agent-harness governance check` to fail on blocking governance
   findings.
5. Run `agent-harness governance export --output .agent-harness/governance/`
   to write stable governance artifacts.
6. Start the existing local operator server with `agent-harness serve` and
   inspect governance data through a read-only Governance section.
7. Run `agent-harness release readiness` and verify governance evidence is part
   of the readiness result.

Governance is an evidence surface, not an execution surface. It must not run
tasks, approve or deny actions, edit policies, edit config, apply templates,
start providers, mutate source artifacts, or create a separate server stack.
The operator Governance section is a read-only evidence browser. Approval
mutation remains in the existing approval panel.

V12 deliberately avoids hosted governance, multi-user authentication,
multi-tenant admin, enterprise control planes, cloud deployment, SOC2 or ISO
readiness claims, formal compliance mapping, remote dashboards, and arbitrary
workspace browsing.

## User Stories

1. As a reviewer, I want one local governance summary, so that I can see the
   project evidence state without inspecting every subsystem manually.
2. As a release maintainer, I want governance checks to fail only on blocking
   findings, so that advisory warnings remain visible without blocking routine
   releases.
3. As a security reviewer, I want governance reports to be redaction-safe, so
   that secrets, raw provider payloads, and unredacted sensitive context never
   appear in reports, API responses, or UI views.
4. As a reviewer, I want optional domains to report `not_present`, so that an
   unused or unimplemented domain is not confused with missing required
   evidence.
5. As a reviewer, I want enabled domains without required evidence to report
   `missing_evidence`, so that real artifact gaps are visible.
6. As a reviewer, I want malformed evidence to become a normalized governance
   finding, so that a bad artifact does not crash the report or disappear.
7. As a policy author, I want policy governance to show what is allowed,
   denied, and approval-gated, so that I can verify policy remains the
   permission ceiling.
8. As an approval reviewer, I want approval governance to distinguish pending,
   approved, denied, stale, failed-binding, and policy-denied states, so that
   decision traceability is reviewable.
9. As a provider user, I want provider governance to expose profiles, trust
   zones, model ids, approval ids, hashes, and redacted artifact availability,
   so that provider use is inspectable without leaking payload contents.
10. As a retrieval reviewer, I want retrieval governance to summarize index,
    backend, embedding, provenance, scorecard, and rejection evidence, so that
    context selection remains deliberate and local-first.
11. As a template reviewer, I want template governance to show installed and
    applied templates, validation status, capabilities, and application
    evidence, so that generated files remain auditable.
12. As a skill reviewer, I want skill governance to show installed skills,
    validation status, sources, risks, and text-only boundaries, so that
    workflow guidance remains local and non-executable.
13. As an MCP reviewer, I want MCP governance to show resources, prompts,
    denial evidence, and access logs, so that MCP cannot bypass policy,
    redaction, or approval rules.
14. As a multi-agent reviewer, I want orchestration governance to show roles,
    authority boundaries, context scopes, handoffs, approvals, timelines, and
    complexity evidence, so that each agent's authority is auditable.
15. As a security reviewer, I want normalized findings across policy, provider,
    retrieval, templates, skills, MCP, orchestration, docs, and release
    readiness, so that risks can be compared consistently.
16. As an operator UI user, I want a Governance section in the existing local
    operator UI, so that I can browse governance evidence without a separate
    server or remote dependency.
17. As a release maintainer, I want release readiness to include governance
    evidence and fail on critical governance findings, so that release
    decisions include the aggregate governance state.
18. As a documentation reviewer, I want docs checks to reject unsupported
    governance, enterprise, and compliance claims, so that V12 is not
    overstated.

## Behavioral Requirements

1. `agent-harness governance summary` prints a concise local governance
   summary for the current project.
2. `agent-harness governance report --format markdown` emits a Markdown
   governance report without mutating source evidence.
3. `agent-harness governance report --format json` emits a JSON
   `governance_report.v1` payload.
4. `agent-harness governance check` exits `0` when no blocking governance
   findings exist.
5. `agent-harness governance check` exits `1` when blocking governance findings
   exist.
6. `agent-harness governance check` exits `2` for invalid input, config, or
   artifact-root errors.
7. `agent-harness governance check` exits `3` for internal errors.
8. `agent-harness governance export --output .agent-harness/governance/`
   writes `governance_summary.v1.json`, `governance_report.v1.md`,
   `governance_report.v1.json`, `governance_index.v1.json`, and
   `governance_findings.v1.json`.
9. Governance does not add `agent-harness governance serve`; the UI is reached
   through existing `agent-harness serve`.
10. Governance reads only known artifact roots and existing configured release
    evidence paths.
11. Governance does not perform arbitrary workspace walks.
12. Governance rejects path traversal artifact references.
13. Governance rejects absolute machine-local artifact references from reports,
    API responses, and UI payloads.
14. Governance records safe project-relative artifact references in
    `governance_index.v1`.
15. Governance records content hashes for indexed artifacts where the artifact
    is safe to hash.
16. Governance never exposes API keys, environment variable values, raw headers,
    raw provider payload contents, or unredacted sensitive context.
17. If raw provider payload artifacts exist, governance reports a finding but
    does not expose or index payload contents.
18. Governance classifies every domain with one of `present`, `not_present`,
    `missing_evidence`, `malformed_evidence`, `blocked_by_policy`, or
    `roadmap_only`.
19. MCP, orchestration, retrieval, template, skill, and provider evidence may
    be absent and should report `not_present` unless a selected release/profile
    policy requires the domain.
20. An enabled or used domain with missing required artifacts reports
    `missing_evidence`.
21. Existing but unparsable evidence reports `malformed_evidence` and produces
    a governance finding.
22. `governance_finding.v1` records finding id, severity, domain, source,
    message, artifact reference, evidence refs, recommendation, and
    `blocks_release`.
23. Critical findings block release readiness by default.
24. High findings block only when policy or check rules map them to
    `blocks_release: true`.
25. Medium, low, and info findings are advisory by default.
26. Policy governance shows available policy profiles, the default profile,
    provider-input behavior, sensitivity classes, approval-gated actions,
    denied actions, scanner thresholds, template capability policy, skill
    rules, MCP resource permissions, and orchestration permissions.
27. Run governance counts total, successful, failed, blocked, approval-gated,
    provider-backed, retrieval-backed, eval-backed, MCP-linked, and
    orchestration-linked runs from known run artifacts.
28. Approval governance counts approval requests and distinguishes pending,
    approved, denied, expired, stale, failed-binding, tamper-failure, and
    policy-denied states where evidence exists.
29. Provider governance summarizes provider profiles, trust zones, model ids,
    network flags, approvals, provider-call counts, redacted artifact
    availability, hashes, token/cost/latency stats when available, provider
    input sensitivity classes, and hard-denied class blocking.
30. Retrieval governance summarizes indexes, backend, embedding backend,
    embedding model/version, `remote_embeddings`, provenance methods,
    scorecards, Precision@k, Recall@k, and denied or sensitive chunk
    rejections where evidence exists.
31. Template governance summarizes bundled templates, local templates,
    versions, sources, applications, `template_application.v1` evidence,
    validation status, generated schema versions, and capabilities.
32. Skill governance summarizes installed skills, versions, sources,
    `skill_validation.v1` evidence, risk indicators, allowed and forbidden
    context, skill pack source, and AGENTS.md presence.
33. MCP governance summarizes exposed resources, prompts, read-only capability
    status, policy filtering evidence, provenance, denied actions, and MCP
    audit events.
34. Multi-agent governance summarizes orchestration runs, roles, boundaries,
    context scopes, handoffs, per-agent tool access, per-agent approvals,
    timelines, findings, and complexity benchmark results.
35. Security findings governance normalizes severity, source, rule id,
    location, status, remediation, blocked-run status, and advisory status.
36. Release readiness governance summarizes latest readiness evidence and
    distinguishes implemented, experimental, roadmap, not implemented, failed,
    warning, and passed statuses.
37. The existing operator API requires `X-Agent-Harness-Operator-Token` for all
    `/api/v1/governance/*` routes.
38. Governance API routes are read-only and do not mutate runs, approvals,
    policies, configs, artifacts, or exports.
39. Governance API routes return redaction-safe domain payloads from artifact
    or storage abstractions.
40. The operator UI includes a Governance section with Overview, Policies,
    Runs, Approvals, Providers, Retrieval, Templates, Skills, MCP,
    Multi-Agent, Security Findings, Release Readiness, and Exports views.
41. The Governance UI uses only local `/api/v1/governance/*` routes and
    packaged static assets.
42. The Governance UI cannot create, approve, deny, delete, edit, rerun, or
    otherwise mutate anything.
43. `agent-harness release readiness` includes governance summary, report,
    check, critical finding, docs claim, and operator governance route evidence.
44. Release readiness fails when critical governance findings exist.
45. Documentation checks reject unsupported implemented claims for hosted
    governance, enterprise control planes, multi-tenant admin, compliance
    readiness, SOC2 readiness, ISO readiness, cloud deployment, and formal
    compliance certification.
46. V12 documentation describes governance outputs as future inputs to the
    `v1.9.0` Compliance Evidence Pack without claiming compliance readiness.

## Implementation Decisions

- Add `agent_harness.governance` as the V12 boundary. It owns aggregation,
  domain status classification, finding normalization, report generation,
  checks, export writing, and operator governance payload construction.
- Keep governance out of `agent_harness.core.runtime`. Governance observes
  artifacts and does not execute tasks or providers.
- Add boundary-owned contracts in `agent_harness.governance.schema` for
  `governance_summary.v1`, `governance_report.v1`, `governance_index.v1`,
  and `governance_finding.v1`.
- Add a first-class domain status enum with `present`, `not_present`,
  `missing_evidence`, `malformed_evidence`, `blocked_by_policy`, and
  `roadmap_only`.
- Add a governance finding severity model with `critical`, `high`, `medium`,
  `low`, and `info`, plus explicit `blocks_release` behavior.
- Add a `governance` CLI command family with `summary`, `report`, `check`, and
  `export`. Do not add `governance serve`.
- Store governance exports under `.agent-harness/governance/` only when the
  user invokes export.
- Reuse existing config loading, policy loading, run storage, orchestration
  storage, MCP resource listing, template registry, skill registry, docs
  checks, release evidence, and operator app patterns.
- Extend the existing local operator API with token-protected read-only
  `/api/v1/governance/*` routes. Do not create a second server stack.
- Extend the packaged vanilla operator UI. Do not introduce Node, a CDN, a
  remote API, browser storage for governance data, or external assets.
- Treat policy as the permission ceiling for governance interpretation. Task,
  template, skill, MCP, or orchestration configuration cannot widen policy.
- Treat raw provider artifacts as evidence of a governance finding, not as
  reportable content.
- Treat optional absent domains as `not_present`, not failed, unless selected
  release or profile policy requires evidence.
- Treat malformed evidence as a normalized finding and keep report generation
  best-effort.
- Release readiness consumes governance outputs as release evidence but does
  not become a compliance certification workflow.

## Testing Decisions

- Test governance through public CLI commands, public operator API routes,
  packaged UI assets, exported governance artifacts, and release readiness
  output.
- Unit tests should cover schema validation, domain status classification,
  finding severity mapping, check exit code semantics, safe artifact reference
  handling, redaction filtering, and count aggregation.
- Integration tests should cover summary generation from fixture runs, Markdown
  and JSON reports, export layout, clean-project checks, seeded blocking
  findings, optional absent domains, missing evidence, malformed evidence,
  operator API routes, UI route usage, and release-readiness integration.
- Adversarial tests should cover raw provider payload artifacts, env var values
  in fixtures, malformed run artifacts, path traversal references, absolute
  path references, roadmap-only feature claims, hard-denied provider input,
  high-risk actions without approval evidence, MCP resources without policy
  evidence, orchestration handoffs without audit evidence, and unsafe
  template/skill evidence.
- Tests should not assert private helper names or internal iteration order
  except where artifact output is explicitly documented as stable.
- Existing operator tests provide the pattern for token enforcement, packaged
  local UI assets, and local API route usage.
- Existing docs-check tests provide the pattern for unsupported claim guards.
- Existing release-readiness tests provide the pattern for adding a new
  evidence gate.

## Out of Scope

- Implementing V12 governance in this planning task.
- `agent-harness governance serve`.
- Hosted governance APIs or dashboards.
- Remote web UI operation.
- Multi-user authentication or authorization.
- Enterprise control plane behavior.
- Multi-tenant governance.
- Cloud deployment.
- SOC2 readiness, ISO readiness, formal compliance certification, or
  compliance mapping.
- Editing policies, configs, runs, approvals, templates, skills, or artifacts
  through governance.
- Creating runs through governance.
- Approving or denying actions through the governance view.
- Applying templates through governance.
- Starting providers or live provider calls through governance.
- MCP tools, MCP writes, or MCP approval mutation through governance.
- Arbitrary filesystem browsing or workspace scans.
- Copying raw provider payloads, secrets, raw headers, raw Qdrant internals, or
  ignored local cache state into governance artifacts.
- Changing default policy behavior based on governance findings.
- Building the future `v1.9.0` Compliance Evidence Pack.

## Further Notes

V12 is intentionally an evidence foundation. It should make local governance
review easier and safer without expanding Agent Harness into organization-wide
governance or compliance tooling. The main implementation risk is scope
creep: governance touches many domains, so each slice should prove one
observable review workflow before adding broader aggregation.

The second risk is accidental disclosure. Provider payloads, environment
values, absolute paths, and denied context must be filtered before they reach
reports, API responses, exports, or UI views.

The third risk is false failure. Optional domains are common in local projects,
so `not_present`, `missing_evidence`, `malformed_evidence`, and
`blocked_by_policy` must remain distinct.
