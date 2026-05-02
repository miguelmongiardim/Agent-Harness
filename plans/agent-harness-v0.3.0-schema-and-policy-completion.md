# Plan: Agent Harness v0.3.0

> Source PRD: [docs/prd-agent-harness-v0.3.0-schema-and-policy-completion.md](../docs/prd-agent-harness-v0.3.0-schema-and-policy-completion.md)

## Delivery Status

Status initialized from the v0.3.0 PRD on 2026-04-26.

- Phase 0: completed
- Phase 1: completed
- Phase 2: completed
- Phase 3: completed
- Phase 4: completed
- Phase 5: completed
- Phase 6: completed
- Phase 7: completed
- Phase 8: completed
- Phase 9: completed
- Phase 10: completed
- v0.3.0 status: closed at `v0.3.0`.
- Next target: start v1.0.0 from [plans/agent-harness-v1.0.0-mature-cli-runtime.md](agent-harness-v1.0.0-mature-cli-runtime.md).

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: v0.3.0 extends the existing CLI. New public commands are
  `migrate schemas` and either `docs check` or `doctor --docs`. Existing
  commands keep their shape unless a v0.3.0 behavior requires additional evidence.
- **Key models**: `HarnessConfig`, `TaskSpec`, `PolicyProfile`,
  `TemplateSpec`, `ProviderCallAudit`, `ProviderInputManifest`,
  `SecurityFinding`, `ContextManifest`, `BenchmarkPackRecord`, and run summary
  evidence remain the public model families. v0.3.0 adds version-aware wrappers or
  fields where original/effective schema evidence is required.
- **Schema**: new public inputs default to `config.v2`, `task.v2`,
  `policy.v2`, and `template.v2`. v0.2.0 inputs remain readable through explicit
  compatibility loaders. Compatibility loading must never widen policy or
  template capabilities.
- **Storage**: run artifacts stay under `.agent-harness/runs/<run-id>` with
  JSON artifacts, append-only events, approvals, checkpoints, and an artifact
  index. Migration and docs-check reports write deterministic JSON and optional
  Markdown artifacts under `.agent-harness/` when useful.
- **Runtime boundary**: the native runtime remains primary. v0.3.0 hardens schema,
  policy, provider, security, retrieval, template, benchmark, docs, demo, and
  release evidence around the existing runtime.
- **Policy boundary**: `policy.v2` is the permission ceiling for provider use,
  provider input, trust zones, scanner thresholds, template capabilities,
  migration behavior, retrieval inclusion, tool execution, exports, and
  approvals.
- **Approval model**: provider-use, provider-input, template apply, patch, and
  `git_commit` approvals remain distinct. v0.3.0 strengthens provider-use approval
  binding; patch and commit approval semantics must not regress.
- **Audit model**: every public workflow added by v0.3.0 emits inspectable evidence:
  migration reports, original/effective schema versions, docs-check reports,
  policy decisions, provider-call hashes, redacted artifacts or summaries,
  security findings, retrieval manifests, template compatibility decisions,
  benchmark exports, and release evidence.
- **Provider boundary**: provider profiles remain configured, named, and
  policy-mediated. Provider-call artifacts do not store raw provider request or
  response payloads by default.
- **External service boundary**: live provider tests, Qdrant/FastEmbed, Gitleaks,
  CycloneDX, and Python 3.13 compatibility are opt-in or advisory. Missing
  optional tools must produce clear diagnostics and not break the default local
  path.
- **Docs boundary**: public docs distinguish implemented behavior from roadmap
  scope. Docs checks are release gates outside `agent-harness eval`.
- **TDD execution**: each phase starts with one public behavior test, then
  repeats red-green-refactor for the remaining acceptance criteria. Do not build
  horizontal infrastructure unless the current or next phase exercises it.

---

## Phase 0: v0.3.0 Public Baseline Walking Skeleton

**User stories covered**

- Story 1: new users start on v0.3.0 schemas.
- Story 4: reviewers can see original and effective schema evidence.
- Story 23: release work has evidence from the start.

**Observable behaviors**

- `agent-harness init` creates `config.v2` and `policy.v2`.
- A bundled v0.3.0 task validates, runs through the existing runtime, and can be
  inspected.
- `inspect run` shows original and effective schema versions for config, task,
  and policy inputs.
- Existing v1 examples still validate through compatibility loading.

**First RED test**

- `tests/integration/test_public_schema_baseline.py::test_init_run_and_inspect_emit_default_schema_evidence`
  should initialize a project, run a minimal v0.3.0 task, inspect the run, and fail
  until the run artifacts record original/effective schema versions.

### GREEN implementation scope

Thread the smallest v0.3.0 default path through `init`, task validation, run, run
artifacts, and inspect output. Keep v1 compatibility narrow: a readable v1 input
normalizes to an effective v0.3.0 contract only when policy and capabilities are not
widened.

### Refactor candidates

- Extract a schema-version evidence helper once both run artifacts and
  migration reports need the same representation.
- Split compatibility-loader code from raw Pydantic models if validation
  branching starts to obscure model contracts.

### Acceptance criteria

- [x] `agent-harness init` emits `config.v2`.
- [x] `agent-harness init` emits default `policy.v2`.
- [x] v0.3.0 examples use `task.v2`.
- [x] A minimal v0.3.0 run completes or pauses exactly as policy requires.
- [x] `inspect run` exposes original and effective schema versions.
- [x] v1 config/task/policy files remain readable where v0.2.0 behavior maps safely
      to v0.3.0.
- [x] Compatibility loading cannot widen provider input, trust-zone, scanner, or
      template capability behavior.

### Phase 0 implementation notes

- Added `schema_versions.json` run artifacts and `inspect run` output for
  original/effective config, task, and policy schema versions.
- New public inputs default to `config.v2`, `task.v2`, and `policy.v2`; v1
  config/task/policy inputs are compatibility-loaded as effective v0.3.0 contracts.
- Compatibility coverage asserts provider-input, trust-zone, and scanner policy
  fields are preserved rather than widened. Template capability widening remains
  structurally unavailable until `template.v2` lands in Phase 7.

### Out of scope

- Schema rewrite command
- Docs gate implementation
- Provider-call artifact hardening beyond schema evidence

---

## Phase 1: Schema Migration Report And Safe Write

**User stories covered**

- Story 2: existing users can keep using v1 workspaces.
- Story 3: maintainers can review schema changes before mutation.
- Story 4: compatibility changes are auditable.

**Observable behaviors**

- `agent-harness migrate schemas` reports proposed upgrades without writing.
- `agent-harness migrate schemas --write` applies safe deterministic upgrades.
- Reports explain unsupported upgrades and files left unchanged.
- Migration preserves or tightens policy behavior; it never loosens it.

**First RED test**

- `tests/integration/test_schema_migration.py::test_migrate_schemas_reports_without_mutating_v1_workspace`
  should create v1 config, task, policy, and template inputs, run report mode,
  assert no files changed, and inspect JSON output for original/effective
  versions and warnings.

### GREEN implementation scope

Add a migration command that discovers known Agent Harness inputs in the current
workspace, normalizes each through compatibility rules, and emits a structured
report. Add `--write` only after report mode is green and safe rewrites are
defined by behavior tests.

### Refactor candidates

- Promote migration report records into schemas once report and `--write`
  coverage share fields.
- Reuse the Phase 0 schema evidence helper rather than duplicating version
  normalization logic.

### Acceptance criteria

- [x] Report mode is the default and does not mutate files.
- [x] Report output includes original schema version, effective schema version,
      changed fields, unchanged fields, warnings, and unsupported upgrade
      reasons.
- [x] `--write` updates only safe config, task, policy, and template schema
      changes.
- [x] `--write` reports skipped files with actionable reasons.
- [x] Migration tests prove v1 policy defaults are not widened.
- [x] Migration output can be stored as an artifact under `.agent-harness/`.

### Phase 1 implementation notes

- Added `agent-harness migrate schemas` with non-mutating report mode by
  default and optional `--output` report storage.
- Added `agent-harness migrate schemas --write` for safe deterministic
  config/task/policy schema upgrades from v1 to effective v0.3.0 contracts.
- Local `template.v1` inputs are discovered and reported but left unchanged with
  an unsupported-upgrade reason until `template.v2` compatibility metadata lands
  in Phase 7.
- Policy migration hydrates flat legacy provider/trust/approval/scanner
  sections and adds the non-permissive template and migration sections without
  widening stricter provider-input decisions.

### Out of scope

- Arbitrary user-defined schema transformations
- Lossy rewrites
- Looser-than-default policy generation

---

## Phase 2: Blocking Docs Check Command

**User stories covered**

- Story 21: docs maintainers can block unsupported public claims.
- Story 23: release managers can treat docs checks as release evidence.

**Observable behaviors**

- `agent-harness docs check` or `agent-harness doctor --docs` scans public docs.
- The check reports unsupported claims, missing implemented-vs-roadmap sections,
  Markdown hygiene failures, broken internal links, citation marker placeholders,
  and schema reference drift.
- Docs checks are not part of `agent-harness eval`.

**First RED test**

- `tests/integration/test_docs_checks.py::test_docs_check_fails_on_unsupported_claim_and_is_not_eval`
  should add a temporary doc with a guarded phrase, assert docs check fails with
  the file path and phrase, and assert `agent-harness eval` does not run docs
  checks.

### GREEN implementation scope

Implement one docs-check CLI path with structured findings and a concise human
summary. Start with guarded claims and required sections, then add link,
Markdown hygiene, citation marker, and schema consistency checks one behavior at
a time.

### Refactor candidates

- Extract individual docs rules behind a shared `DocsFinding` record after at
  least two rules exist.
- Add a schema-reference collector only after guarded-phrase checks are green.

### Acceptance criteria

- [x] Docs checks are available through `agent-harness docs check` or
      `agent-harness doctor --docs`.
- [x] Docs checks are not exposed through `agent-harness eval`.
- [x] Guarded unsupported claims fail with file and line evidence.
- [x] Major docs are required to contain implemented-vs-roadmap sections where
      capability claims are made.
- [x] Internal links are checked.
- [x] Citation marker placeholders are banned.
- [x] Schema references are checked against public schema constants.
- [x] Markdown hygiene failures are reported.
- [x] CI can run docs checks as a blocking job.

### Phase 2 implementation notes

- Added `agent-harness docs check`, which writes `docs_check.v1` reports and
  returns nonzero on findings.
- Docs checks now own guarded unsupported claims, required scope sections,
  internal links, citation placeholders, schema reference drift, and basic
  Markdown hygiene.
- `agent-harness eval` no longer runs or reports docs scanner output.
- CI includes a blocking docs-check job.

### Out of scope

- External link crawling
- Natural-language proof of every claim
- Documentation generation

---

## Phase 3: `policy.v2` Provider-Input Contract

**User stories covered**

- Story 5: `policy.v2` is a real public schema.
- Story 6: the default provider-input matrix is explicit and strict.
- Story 7: tasks and CLI flags cannot widen provider-input behavior.

**Observable behaviors**

- Default policy validates as `policy.v2`.
- Provider-input decisions follow the v0.3.0 matrix exactly.
- Task specs and CLI flags can deny additional sensitivities but cannot turn a
  deny or approval requirement into allow.
- Looser profiles must be explicit, named, documented, and deliberately
  selected.

**First RED test**

- `tests/unit/test_policy_contract.py::test_default_provider_input_matrix_and_non_widening_overrides`
  should validate default `policy.v2`, evaluate each sensitivity class, and fail
  if task or CLI overrides widen any decision.

### GREEN implementation scope

Promote `policy.v2` from v0.2.0-era fields to a direct public schema with explicit
provider-input, trust-zone, approval, scanner, template-capability, and
migration-policy sections. Keep the runtime using the policy engine through its
public evaluation methods.

### Refactor candidates

- Split policy parsing from policy evaluation if `PolicyProfile` becomes too
  broad.
- Add named policy profile metadata only after strict/default behavior is green.

### Acceptance criteria

- [x] `policy.v2` validates independently and is not an alias for `policy.v1`.
- [x] Default provider-input matrix matches the PRD exactly.
- [x] `public` is allowed by default.
- [x] `generated` is allowed only as untrusted evidence.
- [x] `internal` requires provider-input approval.
- [x] `confidential`, `restricted`, and `unknown` are denied by default.
- [x] `secret`, `credential`, `pii`, and `customer` are hard-denied by default.
- [x] Task specs and CLI flags cannot widen the matrix.
- [x] Looser-than-default profiles must be named, explicit, documented, and
      deliberately selected.

### Phase 3 implementation notes

- `policy.v2` defaults now include explicit public contract sections:
  `trust_zones`, `provider_input`, `approvals`, `scanner`,
  `template_capabilities`, and `migration`.
- The runtime keeps using the existing policy engine through compatibility
  mirror fields populated from the v0.3.0 sections, so v1 flat policies remain
  readable while default v0.3.0 is structurally distinct.
- Looser-than-default profiles require a non-default name, documentation, and
  deliberate-selection metadata.

### Out of scope

- Provider-call prompt/response artifact changes
- External DLP backends
- Enterprise policy distribution

---

## Phase 4: Provider Approval Binding And Call Evidence

**User stories covered**

- Story 8: provider-use approvals cannot be reused after operation drift.
- Story 9: provider-call artifacts are auditable without raw payloads.
- Story 10: live provider smoke tests remain opt-in.
- Story 22: provider audit walkthrough has the core evidence path.

**Observable behaviors**

- A provider-use approval binds provider profile, trust zone, model id, provider
  input hash, policy decision id, and checkpoint hash.
- Resume rejects provider execution when any bound field drifts.
- Provider-call artifacts include approval ids, prompt hashes, response hashes,
  redacted prompt/response summaries or artifacts, latency, token metrics where
  available, and policy decision references.
- Raw provider payloads are absent by default.
- Live smoke tests run only with the explicit environment variable and marker.

**First RED test**

- `tests/adversarial/test_provider_approval_binding.py::test_provider_use_approval_denies_provider_input_hash_drift`
  should pause for provider approval, alter provider-bound input evidence, then
  assert resume is denied before any provider call is recorded.

### GREEN implementation scope

Strengthen provider approval payloads and validation before changing provider
transport behavior. Then add redacted provider-call artifact fields and opt-in
live smoke marker coverage.

### Refactor candidates

- Move provider approval binding creation/validation into a dedicated binder
  once both provider-use and provider-input approvals share drift checks.
- Introduce a redacted artifact writer if prompt and response evidence share
  policy-sensitive storage behavior.

### Acceptance criteria

- [x] Provider-use approval binds provider profile, trust zone, model id,
      provider input hash, policy decision id, and checkpoint hash.
- [x] Approval execution rejects provider profile drift.
- [x] Approval execution rejects trust-zone drift.
- [x] Approval execution rejects model-id drift.
- [x] Approval execution rejects provider-input hash drift.
- [x] Approval execution rejects policy-decision-id drift.
- [x] Approval execution rejects checkpoint-hash drift.
- [x] Provider-call artifacts include approval ids.
- [x] Provider-call artifacts include prompt and response hashes.
- [x] Provider-call artifacts include redacted prompt/response artifacts or
      summaries according to policy.
- [x] Provider-call artifacts include latency and token metrics where available.
- [x] Raw provider request/response payloads are not stored by default.
- [x] Live provider tests require
      `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1 uv run pytest -m live_provider`.

### Phase 4 implementation notes

- Provider-use approvals now carry `provider_use_approval_binding.v1` evidence
  for provider profile, trust zone, model id, provider-input hash, provider-use
  policy decision id, and checkpoint hash.
- Approval resume recomputes the current provider-input hash and rejects drift
  before provider execution; adversarial tests cover each bound field.
- Provider-call audit artifacts now include approval ids, prompt and response
  hashes, redacted prompt/response summaries, deterministic latency and token
  metrics, and provider-input policy decision references.
- Recorded/live provider transport uses the documented
  `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS` opt-in boundary, and the
  `live_provider` pytest marker is registered.

### Out of scope

- Mandatory live provider tests
- Raw provider payload capture by default
- New provider transports beyond existing v0.2.0 transports

---

## Phase 5: Security Gates And Advisory Reports

**User stories covered**

- Story 11: first-party findings block risky runs early.
- Story 12: Gitleaks and CycloneDX evidence is advisory by default.
- Story 23: release managers can see advisory reports.

**Observable behaviors**

- Critical first-party secret or security findings block before context,
  provider, or tool execution.
- `SecurityFinding` records include stable policy and evidence fields.
- SARIF exports include policy and security evidence.
- Gitleaks and CycloneDX reports are recorded when available and missing-tool
  warnings are non-blocking by default.

**First RED test**

- `tests/integration/test_security_gates.py::test_critical_secret_blocks_before_context_and_exports_policy_evidence`
  should create a critical first-party finding, run a task, assert no context or
  provider artifact exists, and assert SARIF contains the finding plus policy
  evidence.

### GREEN implementation scope

Harden the existing first-party scanner and SARIF export first. Then add
advisory external scanner/SBOM report detection and artifact upload/recording
without changing default blocking behavior.

### Refactor candidates

- Extract scanner adapters after both advisory integrations share a result
  shape.
- Move SARIF policy evidence formatting into the exporter only after the
  security model has stabilized.

### Acceptance criteria

- [x] Critical first-party findings block before context assembly.
- [x] Critical first-party findings block before provider selection.
- [x] Critical first-party findings block before tool execution.
- [x] `SecurityFinding` records include severity, source, location, evidence,
      policy action, and blocking status.
- [x] SARIF exports include policy and security evidence.
- [x] Gitleaks report availability is detected.
- [x] Gitleaks reports are advisory and non-blocking by default.
- [x] CycloneDX SBOM availability is detected.
- [x] CycloneDX SBOM reports are advisory and non-blocking by default.
- [x] Missing optional scanners produce doctor warnings, not local-run failures.

### Phase 5 implementation notes

- First-party security findings now include stable `source`, `location`,
  `policy_action`, and `blocking` fields while preserving existing scanner,
  path, line, severity, and evidence fields.
- Security gate evaluation annotates findings as `block` or `report` based on
  the active policy threshold before writing `security_findings.json`.
- SARIF security results include policy action, blocking status, source, and
  redacted evidence alongside existing finding and gate metadata.
- Existing Gitleaks and CycloneDX evidence files under
  `.agent-harness/advisories/` are recorded as `advisory_reports.v1` artifacts
  and never block runs by default.
- `doctor` reports explicit non-blocking warnings when optional Gitleaks or
  CycloneDX tooling is unavailable.

### Out of scope

- Making advisory scanners blocking by default
- Enterprise DLP integrations
- Dependency vulnerability policy beyond advisory SBOM evidence

---

## Phase 6: Retrieval Hardening And Local Dense Fixtures

**User stories covered**

- Story 13: lexical retrieval remains deterministic default.
- Story 14: hybrid retrieval manifests are auditable.
- Story 15: missing optional dependencies fall back cleanly.
- Story 19: dense retrieval can appear in benchmark evidence later.

**Observable behaviors**

- Default retrieval remains lexical and deterministic.
- Hybrid manifests record backend, embedding model, index id, chunk ids,
  per-source scores, sensitivity, policy evidence, and provenance.
- Qdrant/FastEmbed is opt-in and exercised only with deterministic local
  fixtures.
- Missing optional dependencies produce doctor warnings and lexical fallback.
- No remote embeddings are used.

**First RED test**

- `tests/integration/test_retrieval_hardening.py::test_missing_dense_dependencies_warn_and_fall_back_to_lexical_manifest`
  should configure dense retrieval without installed extras, run a task, assert
  doctor warns, and assert the manifest records lexical fallback without remote
  embedding behavior.

### GREEN implementation scope

Start with dependency-missing fallback, then extend manifest metadata for local
dense fixtures. Keep dense retrieval behind the existing retrieval interface so
provider input and context policy filtering remain unchanged.

### Refactor candidates

- Extract a retrieval backend manifest record after lexical fallback and dense
  fixture paths both need it.
- Separate Qdrant fixture setup from production server configuration to keep v0.3.0
  scope explicit.

### Acceptance criteria

- [x] Lexical retrieval remains default.
- [x] Lexical fallback is deterministic.
- [x] Hybrid manifests include backend.
- [x] Hybrid manifests include embedding model.
- [x] Hybrid manifests include index id.
- [x] Hybrid manifests include chunk ids and per-source scores.
- [x] Hybrid manifests include sensitivity and policy evidence.
- [x] Qdrant/FastEmbed tests use deterministic local fixtures.
- [x] Missing optional retrieval dependencies produce doctor warnings.
- [x] Missing optional retrieval dependencies fall back gracefully.
- [x] Remote embeddings are not used.
- [x] Production Qdrant server mode is not exposed as v0.3.0 behavior.

### Phase 6 implementation notes

- Runtime retrieval selection now honors `retrieval_backend`: default `lexical`
  uses lexical retrieval only, while `qdrant` is an opt-in request for local
  dense fixture behavior.
- `context_manifest.v2` now includes `retrieval_backend.v1` evidence with
  requested backend, active backend, backend id, embedding model, index id,
  fallback reason, and `remote_embeddings: false`.
- Missing Qdrant/FastEmbed dependencies keep runs on deterministic lexical
  fallback and record `fallback_reason: missing_optional_dependencies`.
- Hybrid coverage opts into `qdrant`, stubs dependency availability, and uses a
  deterministic local dense fixture; no production Qdrant server or remote
  embedding behavior is exposed.

### Out of scope

- Remote embeddings
- Production Qdrant server mode
- Retrieval tuning for deployment scale

---

## Phase 7: `template.v2` Catalog And Python Trio

**User stories covered**

- Story 16: template compatibility metadata is explicit.
- Story 17: incompatible templates fail before writes.
- Story 18: the Python trio templates cover common OSS starts.

**Observable behaviors**

- `template.v2` bundles validate with minimum version, required capabilities,
  generated schema versions, provider/profile requirements, policy
  requirements, retrieval assumptions, and eval/demo metadata.
- `template.v1` bundles remain readable through compatibility loading.
- Applying an incompatible template rejects before write planning.
- Applying a compatible v0.3.0 template records template id and version in
  workspace metadata.

**First RED test**

- `tests/integration/test_template_v2_catalog.py::test_incompatible_template_v2_rejects_before_write_planning`
  should load a v0.3.0 template requiring an unsupported capability, run
  `template apply`, and assert no pending write approval or destination files
  are created.

### GREEN implementation scope

Extend template schemas and registry records just enough for capability
validation, then migrate `python-lib` and add `cli-tool` and `fastapi-service`
with v0.3.0 metadata. Preserve approval-bound apply from v0.2.0.

### Refactor candidates

- Split template compatibility decisions from registry loading if apply and
  show both expose compatibility evidence.
- Add reusable template schema-version generation helpers once two templates
  need the same v0.3.0 generated schema set.

### Acceptance criteria

- [x] `template.v2` validates as a public manifest.
- [x] `template.v2` includes minimum Agent Harness version.
- [x] `template.v2` includes required capabilities.
- [x] `template.v2` includes generated schema versions.
- [x] `template.v2` includes provider/profile requirements.
- [x] `template.v2` includes policy requirements.
- [x] `template.v2` includes retrieval assumptions.
- [x] `template.v2` includes eval or demo metadata.
- [x] `template.v1` bundles remain readable.
- [x] `python-lib` is migrated to v0.3.0 metadata.
- [x] `cli-tool` exists as a v0.3.0 template.
- [x] `fastapi-service` exists as a v0.3.0 template.
- [x] Incompatible templates fail before write planning.
- [x] Workspace metadata records template id and version after successful apply.

### Phase 7 implementation notes

- `TemplateSpec` now accepts `template.v2` manifests with explicit compatibility
  metadata while keeping `template.v1` readable.
- Bundled `python-lib`, `cli-tool`, and `fastapi-service` templates expose v0.3.0
  metadata through `agent-harness template show`.
- Template apply rejects unsupported required template capabilities before run
  artifact creation, approval planning, or destination writes.
- Approval-bound apply and workspace metadata recording from v0.2.0 remain the
  mutation path for compatible templates.

### Out of scope

- External template catalogs
- Remote template discovery
- Non-Python template expansion in v0.3.0

---

## Phase 8: Benchmark Adapter Interfaces

**User stories covered**

- Story 19: benchmark adapters prove real import/run/export behavior.
- Story 20: benchmark artifacts point to real run evidence.
- Story 14: dense retrieval evidence is exercised in at least one benchmark.

**Observable behaviors**

- SWE-bench-style and Terminal-Bench-style miniature sample packs import into
  workspaces.
- Each adapter prepares workspace files, selects policy, runs through Agent
  Harness, maps eval results, and exports benchmark-style results.
- At least one benchmark scenario exercises local dense retrieval fixtures.
- Benchmark exports point to real run evidence.

**First RED test**

- `tests/integration/test_benchmark_v2_adapters.py::test_swebench_style_adapter_import_run_export_points_to_real_run_evidence`
  should import a miniature sample, execute it, and assert the benchmark result
  references an actual run export and artifacts.

### GREEN implementation scope

Formalize adapter interfaces around the existing local sample-pack execution.
Add the smallest dense-retrieval benchmark case after Phase 6 exposes stable
local fixture behavior.

### Refactor candidates

- Separate benchmark pack parsing from adapter execution once both
  SWE-bench-style and terminal-task adapters share import/run/export flow.
- Add a benchmark result evidence validator if export assertions repeat across
  adapters.

### Acceptance criteria

- [x] SWE-bench-style adapter proves task import.
- [x] SWE-bench-style adapter proves workspace preparation.
- [x] SWE-bench-style adapter proves policy selection.
- [x] SWE-bench-style adapter proves run execution.
- [x] SWE-bench-style adapter proves eval result mapping.
- [x] SWE-bench-style adapter proves benchmark-style export.
- [x] Terminal-Bench-style adapter proves the same import/run/export path.
- [x] At least one benchmark scenario exercises local dense retrieval.
- [x] Benchmark artifacts point to real run evidence.
- [x] Full public dataset downloads are not required.

### Phase 8 implementation notes

- Benchmark cases now run through explicit adapter evidence mapping for
  SWE-bench-style and terminal-bench-style local samples.
- `benchmark_result.v1` records adapter id plus evidence for task import,
  workspace preparation, policy selection, run execution, eval result mapping,
  benchmark-style result export, and retrieval backend evidence when present.
- The local sample pack includes a dense-retrieval case that uses bundled files,
  local ingestion, `retrieval_backend: qdrant`, and local dense fixture evidence
  without public dataset downloads.
- Benchmark result artifacts still point to exported real run evidence rather
  than replacing run artifacts with synthetic reports.

### Out of scope

- Full SWE-bench execution
- Full Terminal-Bench execution
- Large dataset downloads
- Benchmark comparability claims

---

## Phase 9: Provider Audit Demo And v0.3.0 Example Migration

**User stories covered**

- Story 22: `provider_audit` becomes the main README walkthrough.
- Story 23: release evidence includes demoable behavior.
- Stories 8 and 9: provider approvals and call artifacts are inspectable.

**Observable behaviors**

- `examples/provider_audit/` runs offline with deterministic mock transport,
  non-mock trust zone, `network: false`, and required provider-use approval.
- The demo proves pause/resume, provider-use approval linkage, provider-input
  policy evidence, redacted provider-call artifacts, inspect output, and JSON,
  Markdown, and SARIF exports.
- `python_refactor` is migrated to v0.3.0 and remains a secondary demo.

**First RED test**

- `tests/e2e/test_provider_audit_demo.py::test_provider_audit_demo_pauses_resumes_and_exports_all_evidence`
  should run the demo task, approve provider use, resume, inspect artifacts, and
  export JSON, Markdown, and SARIF.

### GREEN implementation scope

Build `examples/provider_audit/` as a thin real walkthrough over existing CLI
behavior, not a parallel demo harness. Migrate `python_refactor` after the v0.3.0
schema and policy defaults are stable.

### Refactor candidates

- Extract shared example fixture helpers only if provider audit and
  python_refactor migration duplicate setup substantially.
- Move README command snippets into tested example scripts only if docs drift
  becomes a recurring failure.

### Acceptance criteria

- [x] `examples/provider_audit/` exists.
- [x] The demo uses deterministic mock transport.
- [x] The demo uses a non-mock trust zone.
- [x] The demo sets `network: false`.
- [x] The demo requires provider-use approval.
- [x] The demo proves offline pause/resume.
- [x] The demo records provider approval linkage.
- [x] The demo records provider-input policy evidence.
- [x] The demo records redacted provider-call artifacts.
- [x] The demo is inspectable through `inspect run`.
- [x] The demo exports JSON.
- [x] The demo exports Markdown.
- [x] The demo exports SARIF.
- [x] `python_refactor` is migrated to v0.3.0 as a secondary demo.

### Phase 9 implementation notes

- `examples/provider_audit/` is a runnable v0.3.0 workspace with recorded
  OpenAI-compatible fixture transport, `local_endpoint` trust zone,
  `network: false`, and required provider-use approval.
- The provider audit e2e test copies the real example, proves pause/resume,
  validates provider-use approval binding, checks provider-input policy
  evidence, verifies redacted provider-call artifacts, inspects the run, and
  exports JSON, Markdown, and SARIF.
- Markdown exports now include the task title when the run has a task artifact,
  making example walkthrough exports self-identifying.
- The existing `examples/tasks/python_refactor.json` secondary demo validates
  as `task.v2` and runs as a v0.3.0 dry run.

### Out of scope

- Live provider walkthroughs
- UI walkthroughs
- MCP or multi-agent demos

---

## Phase 10: Docs, CI, And v0.3.0 Release Evidence

**User stories covered**

- Story 21: docs stay aligned with implemented behavior.
- Story 23: release managers can verify v0.3.0 readiness.

**Observable behaviors**

- README, architecture, security, retrieval, template, benchmark, migration,
  roadmap, and changelog docs describe implemented v0.3.0 behavior and isolate
  roadmap items.
- Docs gates pass.
- Local checks pass.
- Remote blocking CI is green for Python 3.11 and 3.12.
- Python 3.13 compatibility is allowed failure if present.
- Advisory scanner/SBOM reports are visible.
- `v0.3.0` is tagged only after release evidence is complete.

**First RED test**

- `tests/integration/test_release_evidence.py::test_release_readiness_report_requires_docs_checks_ci_advisories_and_changelog`
  should build or inspect a release-readiness report and fail until docs gate
  status, local checks, CI status fields, advisory report references, changelog
  entry, and tag target evidence are represented.

### GREEN implementation scope

Update public docs only after their corresponding behavior is implemented.
Add release evidence in the smallest form that can be verified locally, then
wire CI and advisory artifacts into the release checklist.

### Refactor candidates

- Extract release evidence collection if docs checks, local checks, CI status,
  and advisory artifacts need to be consumed by more than one command.
- Keep release automation separate from runtime code unless a public command
  requires it.

### Acceptance criteria

- [x] README uses `provider_audit` as the main walkthrough.
- [x] README documents v0.3.0 defaults without unsupported claims.
- [x] Architecture docs reflect v0.3.0 boundaries.
- [x] Security docs reflect `policy.v2`, provider approvals, and advisory
      scanner scope.
- [x] Retrieval docs reflect lexical default, local dense fixtures, fallback,
      and Qdrant/FastEmbed limits.
- [x] Template docs reflect `template.v2` and Python trio templates.
- [x] Benchmark docs reflect adapter interfaces, miniature samples, dense
      scenario, and no benchmark-comparability claim.
- [x] Migration docs explain report mode and `--write`.
- [x] Roadmap separates v1.0.0/future items: MCP, web API/UI, multi-agent workflows,
      external catalogs, production Qdrant server mode, deployment tuning, and
      enterprise/compliance readiness.
- [x] CHANGELOG includes `v0.3.0`.
- [x] Docs gates pass cleanly.
- [x] Local tests and checks pass.
- [x] Remote blocking CI passes on Python 3.11 and Python 3.12.
- [x] Python 3.13 job is allowed failure if present.
- [x] Non-blocking Gitleaks and CycloneDX advisory reports are visible when
      available.
- [x] Annotated tag `v0.3.0` is pushed after evidence is complete.

### Phase 10 implementation notes

- README now uses `examples/provider_audit/` as the main walkthrough and
  documents v0.3.0 defaults with roadmap exclusions.
- Architecture, security, retrieval, template, benchmark/evaluation, migration,
  release-readiness, and roadmap docs now describe implemented v0.3.0 behavior and
  isolate future work.
- `agent-harness release readiness --version 0.3.0 --ci-run-id <run-id>` writes
  a `release_readiness.v1` report with docs gate status, local check commands,
  target-commit CI evidence, advisory report references, changelog presence,
  and tag target evidence.
- `CHANGELOG.md` includes the `0.3.0` v0.3.0 completion release entry.
- Remote CI run `24962697751` passed for
  `f6fef27c4af6f4dc424ff8b5a96fdd8ceda9a118`, including Python 3.11 and 3.12
  compatibility jobs.
- Annotated tag `v0.3.0` was pushed and dereferences to
  `f6fef27c4af6f4dc424ff8b5a96fdd8ceda9a118`.

### Out of scope

- Enterprise/compliance release claims
- Deployment hardening
- Web/API/UI release artifacts
- MCP or multi-agent release artifacts

## Cross-Phase Invariants

- No subsystem bypasses the policy engine.
- Public input defaults are v0.3.0 after Phase 0.
- v0.2.0/v0.2.0 remains the compatibility baseline.
- Compatibility loading and migration never widen policy or template
  capabilities.
- Task specs and CLI flags can narrow permissions but cannot widen policy
  ceilings.
- `secret`, `credential`, `pii`, and `customer` are hard-denied in the default
  provider-input policy.
- `unknown` is denied in the default provider-input policy.
- Provider trust zone is explicit metadata and is never inferred from endpoint
  URL or `localhost`.
- Provider-use approvals are bound to the exact provider operation and are
  revalidated before execution.
- Raw provider request/response payloads are not stored by default.
- Lexical retrieval remains the deterministic default.
- Dense retrieval is local-only in v0.3.0.
- Missing optional dependencies produce clear diagnostics and graceful fallback.
- External scanner and SBOM integrations are advisory and non-blocking by
  default.
- Benchmark artifacts point to real run evidence.
- Docs checks are release gates and are not part of `agent-harness eval`.
- Public docs distinguish implemented behavior from roadmap items.
- Every phase starts with a public behavior RED test and proceeds
  red-green-refactor one behavior at a time.
- Every new subsystem is exercised by a behavior in the same phase or the
  immediately following phase.
- No v1.0.0/future roadmap feature is implemented without a new PRD or explicit
  scope decision.
