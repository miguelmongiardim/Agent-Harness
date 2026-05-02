# Plan: Agent Harness v0.2.0

> Source PRD: [docs/prd-agent-harness-v0.2.0-provider-retrieval-foundation.md](../docs/prd-agent-harness-v0.2.0-provider-retrieval-foundation.md)

## Delivery Status

Status synced to the repository implementation on 2026-04-26.

- Phase 0: implemented
- Phase 1: implemented
- Phase 2: implemented
- Phase 3: implemented
- Phase 4: implemented
- Phase 5: implemented
- Structure reconciliation: implemented
- Phase 6: implemented
- Phase 7: implemented
- Phase 8: implemented
- Phase 9: implemented
- Next target: v0.2.0 closure review

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: v0.2.0 extends the existing CLI. `run` becomes
  provider-profile-aware, while `inspect`, `export`, `template`, `eval`, and
  `doctor` surface new v0.2.0 evidence without replacing the v0.1.0 command shape.
- **Key models**: `ProviderProfile`, `ProviderCallAudit`,
  `ProviderInputRecord`, `SecurityFinding`, `TemplateRegistryRecord`,
  `BenchmarkPackRecord`, `GitCommitApproval`, and `context_manifest.v2`
  included or rejected item records become the core new v0.2.0 boundary models.
- **Schema**: v0.1.0/v0.2.0 files remain readable where practical, but materially
  changed public contracts move to `v2`, and new writers emit v0.3.0 by default.
- **Storage**: run artifacts remain under `.agent-harness/runs/<run-id>` with
  append-only JSONL evidence and SQLite-backed inspectable metadata; the
  template registry is packaged as read-only SQLite metadata over in-repo
  bundles.
- **Runtime boundary**: the native runtime remains primary. Provider transports
  are model adapters behind a shared provider gateway rather than a new
  framework runtime.
- **Package layout**: core orchestration and models live under
  `agent_harness.core`, context ingestion/retrieval under
  `agent_harness.context`, policy mediation under `agent_harness.policy`, and
  tool execution under `agent_harness.tools`. The report's named source
  packages and leaf modules now exist under `src/agent_harness`. Legacy
  top-level compatibility shims have been removed so new code imports through
  the report-shaped package paths directly.
- **Policy boundary**: policy remains the permission ceiling for provider use,
  provider input, retrieval inclusion, tool execution, template apply,
  security-gate decisions, and `git_commit`.
- **Approval model**: provider-use approval and `git_commit` approval are
  separate from patch approval. Patch approval never implies commit approval.
- **Audit model**: provider calls, provider-bound context, included and
  rejected manifest items, template applies, security findings, and git commit
  actions are all auditable artifacts.
- **External service boundary**: `transport` controls protocol behavior and
  `trust_zone` controls policy behavior. Trust is never inferred from endpoint
  URL or `localhost`.
- **Credential boundary**: provider profiles store env-var names only. Secret
  values are resolved at execution time and are never persisted in config,
  tasks, templates, artifacts, or audit logs.

---

## Phase 0: Provider-Profile-Aware Mock Run

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_provider_profiles.py`
- Main surfaces: `config.v2`, `task.v2`, `run --provider`, recorded
  `provider.json`, and `inspect run` provider metadata.

**User stories covered**

- Story 1: a developer can select a configured provider profile.
- Story 6: credentials and provider metadata are controlled by config.

**Observable behaviors**

- v0.3.0 config accepts provider profiles and a project default.
- A task can select a configured `mock` provider profile.
- `run` and `inspect run` record `provider_profile_id`, `transport`,
  `trust_zone`, `model`, endpoint identity, and network flag.

**First RED test**

- A v0.3.0 task using a configured `mock` provider profile completes, and
  `inspect run` exposes the expected provider metadata from recorded artifacts.

### What to build

Thread provider-profile selection and run-metadata recording through the
existing v0.1.0 runtime without adding real provider calls yet.

### Acceptance criteria

- [x] v0.3.0 provider profiles load from config and validate the required fields.
- [x] Tasks can select a configured provider profile by id, or inherit the
      project default.
- [x] CLI override can switch only to another configured provider profile.
- [x] Run artifacts persist provider metadata and `inspect run` renders it.

### Out of scope

- Real provider transports
- Trust-zone approval pauses
- Provider-input sensitivity filtering

---

## Phase 1: Trust-Zone-Gated Provider Use

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_provider_approval.py` and provider-use
  assertions in `tests/unit/test_policy.py`
- Main surfaces: trust-zone policy evaluation, pending `provider_use`
  approvals before model execution, approval binding to selected provider
  metadata, and run resume after provider approval.

**User stories covered**

- Story 1: configured provider-backed runs are policy-bounded.
- Story 2: trust zones are explicit and not inferred.

**Observable behaviors**

- `mock` is allowed by default.
- `local_process` is allowed only when no network boundary exists.
- `local_endpoint`, `private_network`, and `hosted_provider` require approval
  before provider use.
- `localhost` is not treated as automatically safe.

**First RED test**

- A run using a configured `local_endpoint` or `hosted_provider` profile pauses
  before the first provider call and records a pending provider approval.

### What to build

Add trust-zone policy evaluation and provider-use approval binding in front of
the provider gateway, while keeping the transport interface small.

### Acceptance criteria

- [x] Trust-zone behavior follows policy, not endpoint URL.
- [x] `requires_approval` on the provider profile can only make behavior
      stricter, never looser.
- [x] Task specs and CLI overrides cannot widen trust-zone permissions.
- [x] Provider approval artifacts bind the selected provider profile and trust
      zone before execution continues.

### Out of scope

- Sensitivity-class filtering beyond what approval metadata needs
- Real hosted provider contracts

---

## Phase 2: Provider-Input Sensitivity Gate

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_provider_input.py`
- Main surfaces: richer v0.2.0 sensitivity classes, default provider-input policy
  matrix, `provider_input.json` artifacts, separate `provider_input`
  approvals, deny-only narrowing via task specs and CLI flags, and inspectable
  provider-input policy evidence.

**User stories covered**

- Story 2: provider use respects explicit trust and data boundaries.
- Story 3: denied data never leaves Agent Harness.
- Story 5: rejected evidence is inspectable.

**Observable behaviors**

- Provider-bound context applies `provider_input_policy` per item.
- `generated` items may enter provider input only as untrusted evidence.
- `internal` requires explicit provider-input approval.
- `confidential`, `restricted`, `secret`, `credential`, `pii`, `customer`,
  and `unknown` are denied in the default profile.
- Redaction, reclassification, and reevaluation are recorded when used.

**First RED test**

- A run with mixed sensitivity classes produces provider-input records that
  allow only default-permitted classes and reject the rest with policy
  evidence.

### What to build

Add richer public sensitivity classes, the provider-input policy matrix,
provider-bound context records, hard-deny handling, and policy-decision
evidence.

### Acceptance criteria

- [x] Unlabeled repo files default to `internal`, `generated` remains untrusted
      evidence, and `unknown` defaults to denied.
- [x] The default provider-input matrix matches the accepted v0.2.0 policy.
- [x] Hard-denied classes cannot be overridden by normal run approval.
- [x] CLI flags and task specs can narrow permissions but cannot widen them.
- [x] Provider-bound context records store class, decision, redaction status,
      trust zone, and approval id where applicable.

### Out of scope

- Remote embeddings
- Full retrieval merge pipeline

---

## Phase 3: Recorded Provider Gateway

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_provider_gateway.py`
- Main surfaces: shared `ProviderGateway`, recorded `provider_calls.json`
  artifacts and `provider_call_recorded` events, recorded-fixture
  `openai_compatible` and `anthropic` transports, env-var resolution for
  provider execution, and `inspect run` provider-call evidence.

**User stories covered**

- Story 1: a developer can run through configured real-provider adapters.
- Story 6: credentials are env-var references only.
- Story 11: provider integrations are validated offline by default.

**Observable behaviors**

- `openai_compatible` and `anthropic` transports execute through the common
  provider gateway.
- Local-compatible endpoints use `openai_compatible` transport with explicit
  `trust_zone`.
- Missing required env vars fail clearly.
- Provider audit artifacts record transport, trust zone, model, endpoint
  identity, network flag, and approval linkage.

**First RED test**

- A recorded-fixture `openai_compatible` run completes through the provider
  gateway and emits the expected audit metadata without leaking secret values.

### What to build

Add concrete provider transports, env-var resolution, recorded fixtures, mock
contract coverage, and opt-in live smoke hooks behind the shared gateway.

### Acceptance criteria

- [x] `mock`, `openai_compatible`, and `anthropic` pass contract tests through
      the shared gateway.
- [x] Missing required env vars fail with clear diagnostics that name only the
      env-var key.
- [x] Secret values never enter artifacts or logs.
- [x] Normal CI remains credential-free and offline.

### Out of scope

- Arbitrary CLI-defined providers
- Raw provider payload capture

---

## Phase 4: Hybrid Retrieval Provenance

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_hybrid_retrieval.py` and updated retrieval
  regression coverage in `tests/integration/test_context_retrieval.py`
- Main surfaces: hybrid lexical+dense retrieval coordination,
  `context_manifest.v2` included and rejected items, local dense-retrieval
  metadata, and provider-input records that reference manifest items.

**User stories covered**

- Story 3: provider-bound context is filtered safely.
- Story 4: lexical and dense retrieval both contribute to context.
- Story 5: included and rejected evidence is inspectable.

**Observable behaviors**

- Lexical retrieval and dense retrieval both run as first-class sources.
- Results are normalized, policy-filtered, deduplicated, and merged with
  transparent scores.
- `context_manifest.v2` records included and rejected items with sensitivity
  class, provenance, retrieval method, and policy evidence.
- Dense retrieval records embedding backend and model/version.

**First RED test**

- A run with overlapping lexical and dense hits emits a deduplicated manifest
  that marks items as `lexical`, `dense`, or `both`, while denied items remain
  visible in rejected evidence.

### What to build

Extend retrieval and manifest construction so hybrid evidence becomes a stable,
policy-filtered, inspectable artifact rather than an internal helper detail.

### Acceptance criteria

- [x] Lexical retrieval remains the deterministic baseline and is never
      replaced by dense retrieval.
- [x] Dense retrieval uses local embeddings by default.
- [x] Included and rejected manifest items both carry policy evidence.
- [x] Provider-bound context references manifest items rather than bypassing
      manifest construction.

### Out of scope

- Remote embeddings
- Benchmark-scale retrieval infrastructure

---

## Phase 5: Template Registry And Approval-Bound Apply

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_template_registry.py` and updated template
  CLI assertions in `tests/integration/test_cli.py`
- Main surfaces: packaged SQLite-backed template registry metadata, richer
  `template list/show` output, approval-bound `template apply` runs, and
  workspace metadata recording of applied template id and version.

**User stories covered**

- Story 8: template discovery and application are reusable and auditable.

**Observable behaviors**

- `template list` and `template show` read registry metadata.
- `template apply` validates compatibility before proposing writes.
- Applied template id and version are recorded in workspace metadata.

**First RED test**

- Applying a bundled v0.2.0 template produces approval-bound proposed writes and
  records the selected template version after approval.

### What to build

Introduce the packaged template registry, richer template metadata, and
approval-bound apply flow while keeping actual template bundles in-repo.

### Acceptance criteria

- [x] Registry metadata exposes the agreed v0.2.0 template fields.
- [x] Bundled templates are discoverable without arbitrary filesystem scanning.
- [x] `template apply` uses the mutation approval path rather than direct copy.
- [x] Workspace metadata records applied template id and version.

### Out of scope

- External template catalogs
- Remote template discovery

---

## Structure Reconciliation Before Phase 6

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: focused import and behavior checks plus full repo validation.
- Main surfaces: report-shaped package homes for core, policy, context, tools,
  model, runtimes, templates, storage, telemetry, evals, and exporters while
  preserving existing v0.1.0/v0.2.0 imports.

**Rationale**

The source report's `src/agent_harness` tree is the target layout. Before
adding `git_commit`, the repo now materializes that tree so future phases have
predictable files for policy, context, tool, runtime, model, telemetry, eval,
storage, template, and export work.

**Acceptance criteria**

- [x] `agent_harness.model` is a package with model interfaces and mock model
      implementation.
- [x] `agent_harness.templates`, `agent_harness.storage`,
      `agent_harness.evals`, and `agent_harness.exporters` are packages with
      import-compatible public surfaces.
- [x] `agent_harness.runtimes.native` exposes the native runtime boundary.
- [x] Policy, context, and tool internals are split across the report's leaf
      modules instead of living in single monolithic files.
- [x] Telemetry, runtime adapter, model adapter, and eval support leaves exist
      with explicit unsupported-adapter behavior where implementation is not
      part of the current phase.
- [x] Tests and internal imports use the report-shaped package paths rather
      than legacy top-level compatibility shims.
- [x] Tests are grouped under report-shaped buckets: `tests/unit`,
      `tests/integration`, `tests/adversarial`, `tests/e2e`, and
      `tests/fixtures`.
- [x] Architecture docs state how the deep research layout maps to the current
      implementation.

**Out of scope**

- Implementing live provider calls, LangGraph, MCP, or other optional adapters.

---

## Phase 6: Separate Git Commit Approval

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/adversarial/test_git_commit_approval.py` and commit CLI
  coverage in `tests/integration/test_cli.py`
- Main surfaces: `commit propose`, `git_commit.v1` plan artifacts, separate
  `git_commit` approval records, exact-file staging, parent-HEAD drift checks,
  final-message hash binding, and inspectable commit evidence.

**User stories covered**

- Story 7: commit creation is reviewed separately from patch approval.

**Observable behaviors**

- `git_commit` becomes available only after approved patches are applied and
  required tests or success checks pass.
- The runtime may propose a commit message from the approved diff and run
  summary.
- The reviewer may edit the message before approval.
- The final approved message is immutable for that approval record.
- Commit is denied when approval bindings drift.
- `git_commit` stages only the exact approved file set and does not push,
  switch branches, rebase, or broadly stage the worktree.

**First RED test**

- A commit approval request binds the final approved message hash, and the
  commit is denied if the approved message or parent HEAD changes before
  execution.

### What to build

Add `git_commit` as a separate high-risk tool with exact repository-state
binding, explicit staging of approved files only, and revalidation immediately
before commit creation.

### Acceptance criteria

- [x] No model-generated commit message can be committed without human
      approval.
- [x] Approval binds `run_id`, `action_id`, `tool_name`, `parent_HEAD`, exact
      file set, content hashes, diff hash, final commit message hash, policy
      profile, and checkpoint hash.
- [x] Drift in message, HEAD, file set, hashes, diff, policy profile, or
      checkpoint denies the commit.
- [x] No push, branch switch, rebase, broad staging, or unapproved file
      inclusion is possible through `git_commit`.

### Out of scope

- Push
- Branch mutation
- Rebase
- Broad staging

---

## Phase 7: Benchmark Sample Packs

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_benchmark_packs.py` and benchmark eval
  assertions in `tests/adversarial/test_evals_exports.py`
- Main surfaces: packaged `local-samples` benchmark pack,
  `benchmark list/show/run`, staged local benchmark workspaces,
  `benchmark_result.v1` artifacts, run JSON exports, and eval scorecard mapping
  through `benchmark-sample-packs-run`.

**User stories covered**

- Story 9: benchmark-shaped execution is demonstrated without full benchmark
  infrastructure.

**Observable behaviors**

- Local SWE-bench-style and terminal-task sample packs import into task,
  workspace, policy, eval, and export flows.
- Sample packs run in CI without large downloads.
- Benchmark-shaped result artifacts map back to actual run evidence.
- The SWE-bench-style sample completes through approval-bound patch evidence;
  the terminal-task sample completes without mutation.

**First RED test**

- A local sample benchmark pack imports into a runnable task and produces a
  benchmark-style result artifact from a completed run.

### What to build

Add benchmark adapter interfaces and small local sample packs that exercise the
existing runtime end to end.

### Acceptance criteria

- [x] Sample packs prove task import, workspace prep, policy selection, run
      execution, eval mapping, and benchmark-style export.
- [x] Sample packs run in normal CI without external dataset downloads.
- [x] Result exports reflect actual run evidence rather than synthetic reports.

### Out of scope

- Full public benchmark datasets
- Benchmark-scale execution infrastructure

---

## Phase 8: Security Findings And Pre-Run Gates

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_security_gates.py`, with existing
  adversarial policy and eval suites covering compatibility.
- Main surfaces: `security_findings.v1` artifacts, `SecurityFinding`,
  policy-driven pre-run gate thresholds, SARIF security results, and doctor
  reporting for optional scanners.

**User stories covered**

- Story 10: risky runs fail early through normalized findings and policy
  thresholds.

**Observable behaviors**

- Required first-party checks run before execution.
- Findings normalize into `SecurityFinding`.
- Policy thresholds decide whether the run may proceed.
- Findings export to SARIF.
- Missing optional external scanners are reported by `doctor`, not treated as
  normal local-run failures.

**First RED test**

- A high-severity required finding blocks the run before provider execution and
  appears in normalized scanner artifacts.

### What to build

Add pre-run finding normalization, graded threshold evaluation, doctor
reporting for optional scanners, and SARIF export integration.

### Acceptance criteria

- [x] Critical findings always fail.
- [x] High findings fail by default unless policy relaxes them.
- [x] Medium, low, and info are report-only by default.
- [x] Required first-party checks always run.
- [x] Optional external tools contribute findings when available without making
      normal local runs brittle.

### Out of scope

- Mandatory optional-scanner presence for local development
- Security-tool orchestration beyond normalized finding import

---

## Phase 9: Optional LangGraph Boundary Proof

**Implementation status**

- Implemented on 2026-04-26 in the current working tree.
- Coverage: `tests/integration/test_langgraph_runtime_adapter.py`
- Main surfaces: optional `langgraph` extra, `run --runtime langgraph`,
  lazy adapter loading, `runtime_adapter.v1` evidence, and `inspect run`
  runtime-adapter output.

**User stories covered**

- Story 12: boundary compatibility can be demonstrated without replacing the
  native runtime.

**Observable behaviors**

- An optional LangGraph extra can execute one minimal audited run.
- The run emits the same core policy, approval, and audit evidence expected
  from the native runtime.

**First RED test**

- A minimal LangGraph-backed run emits the same core audit artifacts and policy
  evidence expected from the native runtime for the covered path.

### What to build

Add the smallest compatibility layer needed to prove boundary alignment without
chasing feature parity.

### Acceptance criteria

- [x] LangGraph remains optional and isolated behind an extra.
- [x] The native runtime remains the primary execution path.
- [x] Shared policy and audit invariants still hold for the covered path.

### Out of scope

- Full LangGraph parity
- LangGraph as the primary runtime

## Cross-Phase Invariants

- No subsystem bypasses the policy engine.
- Trust zone is explicit metadata and is never inferred from endpoint URLs.
- Task specs and CLI flags can narrow permissions but never widen policy
  ceilings.
- `secret`, `credential`, `pii`, and `customer` never enter provider input in
  the default profile.
- Included and rejected context evidence remain inspectable.
- All external effects are auditable.
- `git_commit` remains a separate approval step from patch approval.
- Normal CI stays credential-free and free of outbound model calls unless
  explicitly running opt-in live tests.
- Every new subsystem is exercised by a behavior in the same phase or the
  immediately following phase.
- Public docs and roadmap claims must not outrun implemented behavior.
