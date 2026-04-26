# PRD: Agent Harness V2

## Problem Statement

Agent Harness V1 closed the v0.2.0 baseline as a credible local-first,
policy-gated agent workflow harness. It now has configured provider profiles,
provider-input gates, hybrid context manifests, approval-bound template
application, separate `git_commit` approval, packaged benchmark sample packs,
security findings, audit artifacts, evals, and an optional LangGraph boundary
proof.

That baseline is strong enough for a pre-1.0 infrastructure prototype, but the
public contract is still uneven for a v0.3.0 release:

- some public inputs still default to v1 schemas while V2 behavior exists
- `policy.v2` and `template.v2` are not yet first-class release contracts
- migration, compatibility evidence, and original/effective schema recording
  are not yet a coherent user workflow
- provider approvals and provider-call evidence need stronger binding and safer
  artifact defaults
- docs do not yet have blocking checks for unsupported claims, schema drift, and
  roadmap scoping
- security, retrieval, template, benchmark, demo, and release evidence need a
  completion pass rather than more prototype-only additions

This matters for maintainers, reviewers, and serious users evaluating Agent
Harness as an OSS infrastructure prototype. Without V2, the repo can demonstrate
interesting controlled-agent behavior, but it cannot cleanly explain what is
implemented, what remains roadmap-only, which schemas are public defaults, how
legacy inputs migrate, and which evidence gates must pass before a v0.3.0
release.

## Solution

Agent Harness V2 is a completion release targeting `v0.3.0`. It establishes the
public V2 contract first, then hardens provider and policy handling, security
findings, retrieval manifests, template manifests, benchmark adapters, demos,
docs, and release evidence.

From a user perspective, V2 should make the default path clear:

- `agent-harness init`, examples, templates, docs, and demos emit V2 schemas by
  default
- v1 inputs remain readable through compatibility loaders
- users can run `agent-harness migrate schemas` to see what would change, and
  can opt into safe rewrites with `--write`
- each run records original and effective schema versions in artifacts
- `policy.v2` defines the provider-input, trust-zone, approval, scanner,
  template-capability, and migration-policy contract directly
- provider use pauses only when policy requires it, and approval records are
  bound tightly enough to prevent stale or widened execution
- provider-call artifacts record enough redacted evidence to audit behavior
  without storing raw provider payloads by default
- docs checks are exposed as `agent-harness docs check` or
  `agent-harness doctor --docs`, not hidden inside `eval`
- release readiness is proven through local checks, blocking CI, non-blocking
  advisory reports, docs gates, changelog update, and tag push

V2 deliberately remains pre-1.0. It does not claim enterprise readiness,
production readiness, compliance readiness, full security, autonomous coding
platform behavior, MCP support, multi-agent support, external template catalogs,
web API/UI support, production Qdrant server mode, large benchmark dataset
execution, or deployment tuning.

## User Stories

1. As a new user, I want `agent-harness init` and examples to default to V2
   schemas, so that I start on the current public contract.
2. As an existing user, I want v1 inputs to remain readable, so that v0.2.0
   workspaces do not break when the project moves to v0.3.0.
3. As a maintainer, I want a schema migration report mode, so that I can review
   compatibility changes before mutating project files.
4. As a reviewer, I want run artifacts to record original and effective schema
   versions, so that I can audit whether compatibility loading changed a run.
5. As a security reviewer, I want `policy.v2` to be a real schema, so that
   provider input, trust zones, approvals, scanner handling, template
   capabilities, and migration policy are not implicit or aliased behavior.
6. As a policy author, I want the default provider-input matrix to be strict and
   explicit, so that public, generated, internal, confidential, restricted,
   secret, credential, pii, customer, and unknown data have predictable
   handling.
7. As a reviewer, I want task specs and CLI flags to only narrow provider-input
   permissions, so that a task cannot widen policy by choosing permissive
   options.
8. As a maintainer, I want provider-use approvals bound to provider profile,
   trust zone, model id, input hash, policy decision id, and checkpoint hash, so
   that approvals cannot be reused for a changed provider operation.
9. As a reviewer, I want provider-call artifacts with approval ids, prompt and
   response hashes, redacted prompt or response artifacts, summaries, latency,
   and token metrics, so that provider behavior can be audited without storing
   raw payloads by default.
10. As a contributor, I want live provider smoke tests to be opt-in only, so
    that normal CI remains deterministic and credential-free.
11. As a security reviewer, I want normalized security findings and pre-run
    thresholds, so that critical first-party issues block before context or
    provider execution.
12. As a maintainer, I want Gitleaks and CycloneDX SBOM reports to be advisory
    artifacts when available, so that release evidence improves without making
    optional local tooling brittle.
13. As a user, I want lexical retrieval to remain the deterministic default, so
    that V2 runs stay reproducible without optional dense-retrieval dependencies.
14. As a retrieval reviewer, I want hybrid manifests to record backend,
    embedding model, index id, chunk ids, scores, sensitivity, policy evidence,
    and provenance, so that dense retrieval can be audited.
15. As a user without Qdrant or FastEmbed installed, I want doctor warnings and
    graceful fallback, so that missing optional retrieval extras do not break
    default local workflows.
16. As a template author, I want `template.v2` manifests with version,
    capability, schema, provider, policy, retrieval, and demo metadata, so that
    template compatibility is explicit.
17. As a user applying a template, I want incompatible templates to fail with a
    clear error before writes, so that scaffolding cannot silently create an
    unsupported workspace.
18. As a maintainer, I want V2 Python trio templates for `python-lib`,
    `cli-tool`, and `fastapi-service`, so that the main template catalog covers
    common Python OSS workflows.
19. As a benchmark maintainer, I want SWE-bench-style and Terminal-Bench-style
    adapter interfaces tested against miniature sample packs, so that adapter
    behavior is real without downloading large datasets.
20. As a reviewer, I want benchmark result artifacts to point to real run
    evidence, so that benchmark exports are not synthetic reports.
21. As a docs maintainer, I want blocking docs checks for claims, Markdown
    hygiene, internal links, required sections, citation marker bans, and schema
    consistency, so that public docs stay aligned with the implemented system.
22. As a release manager, I want `examples/provider_audit/` to be the main
    README walkthrough, so that V2 demonstrates provider approval and audit
    evidence with deterministic offline behavior.
23. As a release manager, I want a v0.3.0 release gate with local checks,
    remote blocking CI, advisory report visibility, clean docs gates, changelog
    update, and tag push, so that the completion release has reviewable
    evidence.

## Behavioral Requirements

1. `agent-harness init` emits `config.v2` and `policy.v2` by default.
2. Bundled examples, demos, and templates use `config.v2`, `task.v2`,
   `policy.v2`, and `template.v2` where those schemas are public inputs.
3. The loader accepts v1 config, task, policy, and template inputs through
   compatibility paths when the legacy input can be safely interpreted.
4. Compatibility loading does not silently widen policy permissions or template
   capabilities.
5. `agent-harness migrate schemas` defaults to a non-mutating report or check
   mode.
6. `agent-harness migrate schemas --write` rewrites only safe, deterministic
   schema upgrades and reports files it did not change.
7. Migration reports show original schema version, proposed effective schema
   version, changed fields, unchanged fields, warnings, and unsupported upgrade
   reasons.
8. Run artifacts record original and effective schema versions for config,
   task, policy, and template inputs that affected the run.
9. `examples/provider_audit/` exists as a V2 demo skeleton and uses deterministic
   mock transport with a non-mock trust zone, `network: false`, and required
   provider-use approval.
10. Major docs include implemented-vs-roadmap sections where public capability
    claims are made.
11. Docs checks detect unsupported claims, Markdown hygiene failures, broken
    internal links, missing required sections, citation marker placeholders, and
    schema consistency drift.
12. Docs checks are exposed through `agent-harness docs check` or
    `agent-harness doctor --docs`.
13. Docs checks are not exposed as `agent-harness eval` scenarios.
14. `policy.v2` validates as its own public schema and is not an alias for
    `policy.v1`.
15. `policy.v2` includes first-class sensitivity classes, provider-input rules,
    trust-zone rules, provider approval rules, external scanner handling,
    template capability rules, and migration policy.
16. The default provider-input policy matrix is:
    `public: allow`,
    `generated: allow_untrusted`,
    `internal: approval_required`,
    `confidential: deny`,
    `restricted: deny`,
    `secret: deny`,
    `credential: deny`,
    `pii: deny`,
    `customer: deny`,
    and `unknown: deny`.
17. `public` content may be sent to providers by default.
18. `generated` content may be sent to providers only as untrusted evidence.
19. `internal` content requires explicit provider-input approval before
    provider submission.
20. `confidential` and `restricted` content are denied by the default profile.
21. `secret`, `credential`, `pii`, and `customer` content are hard-denied by the
    default profile.
22. `unknown` content is denied by the default profile.
23. Task specs and CLI flags can narrow provider-input handling but cannot widen
    the active policy matrix.
24. Custom policy profiles may be stricter than the default profile.
25. A profile looser than the default profile must be explicit, named,
    documented, and deliberately selected.
26. Provider-use approval records bind provider profile, trust zone, model id,
    provider input hash, policy decision id, and checkpoint hash.
27. A provider-use approval is rejected if any bound provider profile, trust
    zone, model id, provider input hash, policy decision id, or checkpoint hash
    changes before execution.
28. Provider-call artifacts record approval ids, prompt hashes, response hashes,
    redacted prompt artifacts or summaries as allowed by policy, redacted
    response artifacts or summaries as allowed by policy, latency metrics where
    available, token metrics where available, and policy decision references.
29. Raw provider request and response payloads are not stored by default.
30. Live provider smoke tests run only when
    `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1 uv run pytest -m live_provider` is
    explicitly selected.
31. First-party critical secret or security findings block runs before context
    assembly, provider selection, or tool execution.
32. Security findings normalize into a stable `SecurityFinding` contract with
    severity, source, location, evidence, policy action, and blocking status.
33. SARIF exports include policy and security evidence for findings that
    affected the run.
34. Gitleaks reports are advisory and non-blocking by default when the scanner
    is available.
35. CycloneDX SBOM reports are advisory and non-blocking by default when the
    tooling is available.
36. Advisory scanner and SBOM artifacts are uploaded or recorded when available,
    and their absence is reported without failing normal local runs.
37. Lexical local retrieval remains the deterministic default retrieval mode.
38. Hybrid lexical+dense retrieval manifests record backend, embedding model,
    index id, chunk ids, per-source scores, sensitivity, policy evidence, and
    provenance.
39. Dense retrieval uses only local embedding paths in V2.
40. Qdrant and FastEmbed support is opt-in and tested with deterministic local
    fixtures.
41. Missing optional retrieval dependencies produce clear doctor warnings and
    graceful fallback to lexical retrieval.
42. V2 does not use remote embeddings.
43. V2 does not support production Qdrant server mode.
44. `template.v2` manifests include minimum Agent Harness version, required
    capabilities, generated schema versions, provider and profile requirements,
    policy requirements, retrieval assumptions, and eval or demo metadata.
45. Template loaders can read `template.v1` bundles through compatibility paths.
46. V2 includes `python-lib`, `cli-tool`, and `fastapi-service` template bundles
    with V2 metadata.
47. Template application rejects incompatible templates before write planning
    with a clear validation error.
48. Template application records template id and template version in workspace
    metadata.
49. Benchmark adapters expose real import, workspace preparation, policy
    selection, run execution, eval result mapping, and benchmark-style result
    export behavior for miniature bundled sample packs.
50. SWE-bench-style and Terminal-Bench-style sample packs run without public
    dataset downloads.
51. At least one benchmark scenario exercises dense retrieval through local
    deterministic fixtures.
52. Benchmark artifacts point to real run evidence and do not replace run
    artifacts with synthetic reports.
53. `examples/provider_audit/` is the main README walkthrough for V2.
54. The `provider_audit` demo proves offline pause/resume, provider-use
    approval, provider-input policy evidence, redacted provider-call artifacts,
    inspect output, and JSON, Markdown, and SARIF exports.
55. The existing `python_refactor` demo is migrated to V2 and remains available
    as a secondary demo.
56. Release readiness for `v0.3.0` requires local checks, remote blocking CI
    green, visible non-blocking advisory reports, changelog update, clean docs
    gates, and pushed release tag.
57. Blocking CI supports Python 3.11 and Python 3.12.
58. Python 3.13 may run as an allowed-failure compatibility job.

## Implementation Decisions

- **Release boundary**: V2 targets `v0.3.0` as a pre-1.0 completion release,
  not as a product expansion release.
- **Compatibility baseline**: V1/v0.2.0 is closed and remains the compatibility
  baseline for v1 loaders and migration behavior.
- **Core system boundary**: V2 remains CLI-first, local-first, and
  evidence-first. It hardens the current runtime, schemas, policy, artifacts,
  docs, and demos rather than adding web, MCP, multi-agent, or deployment
  surfaces.
- **Schema strategy**: public input defaults move to `config.v2`, `task.v2`,
  `policy.v2`, and `template.v2`. Compatibility loaders preserve readable v1
  inputs without hiding the effective schema used by a run.
- **Migration module**: schema migration is a public workflow with report mode
  by default and safe rewrites only under `--write`.
- **Run evidence strategy**: original and effective schema versions become part
  of run evidence so reviewers can distinguish legacy input from normalized
  execution.
- **Docs gate module**: docs checks are a release-quality gate owned outside the
  eval suite. They check public claims, schema references, required sections,
  links, citation placeholders, and Markdown hygiene.
- **Policy module**: `policy.v2` owns provider-input policy, trust-zone rules,
  provider approvals, scanner policy, template capability policy, and migration
  policy as explicit schema fields.
- **Provider-input policy ceiling**: task specs and CLI flags remain narrowing
  mechanisms only. Looser-than-default profiles are allowed only as explicit,
  named, documented, deliberately selected profiles.
- **Approval boundary**: provider-use approvals bind provider profile, trust
  zone, model id, provider input hash, policy decision id, and checkpoint hash.
  Execution revalidates these bindings immediately before provider use.
- **Provider-call artifact boundary**: artifacts store approval references,
  hashes, redacted content or summaries, and metrics. Raw provider payload
  capture remains off by default.
- **Live-provider testing boundary**: live provider tests use a `live_provider`
  marker and the explicit `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1` opt-in.
- **Security module**: first-party security findings are normalized and can
  block before a run proceeds. External scanner and SBOM integrations are
  advisory by default.
- **Retrieval module**: lexical retrieval remains deterministic default.
  Dense retrieval is local-only, opt-in, and manifest-backed. Qdrant/FastEmbed
  behavior is fixture-tested and falls back cleanly when extras are missing.
- **Template module**: `template.v2` carries compatibility, capability,
  provider, policy, retrieval, schema, and demo metadata. Apply rejects
  incompatible templates before write planning.
- **Bundled template scope**: V2 focuses on a Python trio:
  `python-lib`, `cli-tool`, and `fastapi-service`.
- **Benchmark module**: adapter interfaces must import sample packs, prepare
  workspaces, choose policy, execute runs, map eval results, and export
  benchmark-style results that point to real run evidence.
- **Demo strategy**: `provider_audit` is the primary README walkthrough because
  it exercises V2's provider approval and audit identity. `python_refactor`
  remains a secondary demo after schema migration.
- **Release strategy**: release evidence includes local validation, remote
  blocking CI, advisory scanner visibility, docs gate output, changelog update,
  and tag push.
- **Deep modules**: the main V2 deep modules are the schema compatibility and
  migrator boundary, docs checker, policy.v2 evaluator, provider approval
  binder, provider-call artifact recorder, security finding normalizer, scanner
  advisory reporter, retrieval manifest coordinator, template.v2 manifest
  validator, benchmark adapter interface, and demo/release evidence harness.

## Testing Decisions

- Good V2 tests verify behavior through public CLI commands, loaders, runtime
  entry points, run artifacts, inspect output, exports, docs-check commands,
  template apply behavior, benchmark adapter outputs, and release evidence.
- Tests should not depend on private function names or exact internal module
  layout unless a module is itself a public boundary.
- Highest-risk behaviors are:
  schema migration without policy widening,
  effective schema evidence,
  `policy.v2` provider-input enforcement,
  hard-denied sensitivity handling,
  approval binding drift,
  raw provider payload leakage,
  first-party security blocking,
  optional scanner non-blocking behavior,
  hybrid retrieval provenance,
  template capability rejection,
  docs claim drift,
  and benchmark artifacts pointing to real run evidence.
- Schema/default tests must cover V2 scaffolding, v1 compatibility loading,
  migration report mode, migration `--write`, and original/effective schema
  artifact evidence.
- Provider audit end-to-end tests must cover offline pause/resume, provider-use
  approval linkage, provider-input policy, redacted provider-call artifacts,
  inspect output, and JSON, Markdown, and SARIF exports.
- Policy tests must prove task specs and CLI flags cannot widen `policy.v2`.
- Security tests must cover first-party findings, severity thresholds, critical
  secret blocking, SARIF export, and advisory report visibility.
- Retrieval tests must cover deterministic lexical fallback, local dense
  retrieval, optional Qdrant/FastEmbed fixture behavior, dependency-missing
  fallback, and policy-filtered manifests.
- Template tests must cover V2 metadata validation, capability rejection, V2
  scaffolding, template id/version workspace metadata, and v1 template
  compatibility.
- Benchmark tests must cover SWE-bench-style and terminal-task adapter
  import/run/export paths and at least one dense retrieval benchmark scenario.
- Docs CI tests must cover guarded phrases, roadmap scoping, Markdown checks,
  internal links, required sections, citation marker bans, and schema
  consistency.
- Live provider smoke tests are optional validation only and must not be normal
  CI or release criteria.
- Blocking CI must run on Python 3.11 and Python 3.12. Python 3.13 may be
  allowed failure while compatibility is evaluated.
- V2 acceptance is defined by observable behavior across V2 defaults,
  compatibility migration, policy.v2 enforcement, provider audit artifacts,
  security gates, retrieval manifests, template compatibility, benchmark
  adapters, docs gates, and release evidence.

## Out of Scope

- Enterprise-ready, production-ready, compliance-ready, or fully secure claims.
- Autonomous coding platform claims.
- MCP support.
- Web API or web UI.
- Multi-agent workflows.
- External template catalogs.
- Production Qdrant server mode.
- Remote embeddings.
- Full public benchmark dataset execution.
- Large dataset downloads.
- Deployment tuning.
- Enterprise identity, secrets management, DLP, compliance, or multi-tenant
  guarantees.
- Mandatory live provider tests in CI.
- Making advisory external scanner or SBOM reports blocking by default.
- Exposing docs checks through `agent-harness eval`.

## Further Notes

- V2 should be implemented as vertical slices in the stated phase order:
  public baseline, provider and policy completion, security findings and gates,
  retrieval hardening, template catalog expansion, benchmark adapters, then
  demo/docs/release hardening.
- The main product risk is claim drift: docs, examples, and schema defaults
  could imply support beyond the implemented pre-1.0 contract. Blocking docs
  checks exist to control that risk.
- The main security risk is policy erosion while making provider workflows more
  usable. V2 should bias toward explicit denials, approval binding, redacted
  artifacts, and non-widening compatibility behavior.
- The main operational risk is optional tooling brittleness. Dense retrieval,
  Qdrant/FastEmbed, Gitleaks, CycloneDX, live providers, and Python 3.13
  compatibility should provide useful evidence without breaking the default
  local path.
- After PRD acceptance, the next artifact should be a vertical-slice
  implementation plan under `plans/` that maps each phase to acceptance tests,
  public interfaces, and release evidence.
