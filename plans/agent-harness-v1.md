# Plan: Agent Harness V1

> Source PRD: [docs/prd-agent-harness-v1.md](/C:/Users/mmarque9/agent_harness/docs/prd-agent-harness-v1.md)

## Delivery Status

Status synced to the repository implementation on 2026-04-26.

- Phase 0: implemented
- Phase 1: implemented
- Next target: Phase 2

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: V1 extends the existing CLI. `run` becomes
  provider-profile-aware, while `inspect`, `export`, `template`, `eval`, and
  `doctor` surface new V1 evidence without replacing the V0 command shape.
- **Key models**: `ProviderProfile`, `ProviderCallAudit`,
  `ProviderInputRecord`, `SecurityFinding`, `TemplateRegistryRecord`,
  `BenchmarkPackRecord`, `GitCommitApproval`, and `context_manifest.v2`
  included or rejected item records become the core new V1 boundary models.
- **Schema**: V0/V1 files remain readable where practical, but materially
  changed public contracts move to `v2`, and new writers emit V2 by default.
- **Storage**: run artifacts remain under `.agent-harness/runs/<run-id>` with
  append-only JSONL evidence and SQLite-backed inspectable metadata; the
  template registry is packaged as read-only SQLite metadata over in-repo
  bundles.
- **Runtime boundary**: the native runtime remains primary. Provider transports
  are adapters behind a shared provider gateway rather than a new framework
  runtime.
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
- Coverage: `tests/test_v1_phase0_provider_profiles.py`
- Main surfaces: `config.v2`, `task.v2`, `run --provider`, recorded
  `provider.json`, and `inspect run` provider metadata.

**User stories covered**

- Story 1: a developer can select a configured provider profile.
- Story 6: credentials and provider metadata are controlled by config.

**Observable behaviors**

- V2 config accepts provider profiles and a project default.
- A task can select a configured `mock` provider profile.
- `run` and `inspect run` record `provider_profile_id`, `transport`,
  `trust_zone`, `model`, endpoint identity, and network flag.

**First RED test**

- A V2 task using a configured `mock` provider profile completes, and
  `inspect run` exposes the expected provider metadata from recorded artifacts.

### What to build

Thread provider-profile selection and run-metadata recording through the
existing V0 runtime without adding real provider calls yet.

### Acceptance criteria

- [x] V2 provider profiles load from config and validate the required fields.
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
- Coverage: `tests/test_v1_phase1_provider_approval.py` and provider-use
  assertions in `tests/test_policy.py`
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

- [ ] Unlabeled repo files default to `internal`, `generated` remains untrusted
      evidence, and `unknown` defaults to denied.
- [ ] The default provider-input matrix matches the accepted V1 policy.
- [ ] Hard-denied classes cannot be overridden by normal run approval.
- [ ] CLI flags and task specs can narrow permissions but cannot widen them.
- [ ] Provider-bound context records store class, decision, redaction status,
      trust zone, and approval id where applicable.

### Out of scope

- Remote embeddings
- Full retrieval merge pipeline

---

## Phase 3: Recorded Provider Gateway

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

- [ ] `mock`, `openai_compatible`, and `anthropic` pass contract tests through
      the shared gateway.
- [ ] Missing required env vars fail with clear diagnostics that name only the
      env-var key.
- [ ] Secret values never enter artifacts or logs.
- [ ] Normal CI remains credential-free and offline.

### Out of scope

- Arbitrary CLI-defined providers
- Raw provider payload capture

---

## Phase 4: Hybrid Retrieval Provenance

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

- [ ] Lexical retrieval remains the deterministic baseline and is never
      replaced by dense retrieval.
- [ ] Dense retrieval uses local embeddings by default.
- [ ] Included and rejected manifest items both carry policy evidence.
- [ ] Provider-bound context references manifest items rather than bypassing
      manifest construction.

### Out of scope

- Remote embeddings
- Benchmark-scale retrieval infrastructure

---

## Phase 5: Template Registry And Approval-Bound Apply

**User stories covered**

- Story 8: template discovery and application are reusable and auditable.

**Observable behaviors**

- `template list` and `template show` read registry metadata.
- `template apply` validates compatibility before proposing writes.
- Applied template id and version are recorded in workspace metadata.

**First RED test**

- Applying a bundled V1 template produces approval-bound proposed writes and
  records the selected template version after approval.

### What to build

Introduce the packaged template registry, richer template metadata, and
approval-bound apply flow while keeping actual template bundles in-repo.

### Acceptance criteria

- [ ] Registry metadata exposes the agreed V1 template fields.
- [ ] Bundled templates are discoverable without arbitrary filesystem scanning.
- [ ] `template apply` uses the mutation approval path rather than direct copy.
- [ ] Workspace metadata records applied template id and version.

### Out of scope

- External template catalogs
- Remote template discovery

---

## Phase 6: Separate Git Commit Approval

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

**First RED test**

- A commit approval request binds the final approved message hash, and the
  commit is denied if the approved message or parent HEAD changes before
  execution.

### What to build

Add `git_commit` as a separate high-risk tool with exact repository-state
binding, explicit staging of approved files only, and revalidation immediately
before commit creation.

### Acceptance criteria

- [ ] No model-generated commit message can be committed without human
      approval.
- [ ] Approval binds `run_id`, `action_id`, `tool_name`, `parent_HEAD`, exact
      file set, content hashes, diff hash, final commit message hash, policy
      profile, and checkpoint hash.
- [ ] Drift in message, HEAD, file set, hashes, diff, policy profile, or
      checkpoint denies the commit.
- [ ] No push, branch switch, rebase, broad staging, or unapproved file
      inclusion is possible through `git_commit`.

### Out of scope

- Push
- Branch mutation
- Rebase
- Broad staging

---

## Phase 7: Benchmark Sample Packs

**User stories covered**

- Story 9: benchmark-shaped execution is demonstrated without full benchmark
  infrastructure.

**Observable behaviors**

- Local SWE-bench-style and terminal-task sample packs import into task,
  workspace, policy, eval, and export flows.
- Sample packs run in CI without large downloads.
- Benchmark-shaped result artifacts map back to actual run evidence.

**First RED test**

- A local sample benchmark pack imports into a runnable task and produces a
  benchmark-style result artifact from a completed run.

### What to build

Add benchmark adapter interfaces and small local sample packs that exercise the
existing runtime end to end.

### Acceptance criteria

- [ ] Sample packs prove task import, workspace prep, policy selection, run
      execution, eval mapping, and benchmark-style export.
- [ ] Sample packs run in normal CI without external dataset downloads.
- [ ] Result exports reflect actual run evidence rather than synthetic reports.

### Out of scope

- Full public benchmark datasets
- Benchmark-scale execution infrastructure

---

## Phase 8: Security Findings And Pre-Run Gates

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

- [ ] Critical findings always fail.
- [ ] High findings fail by default unless policy relaxes them.
- [ ] Medium, low, and info are report-only by default.
- [ ] Required first-party checks always run.
- [ ] Optional external tools contribute findings when available without making
      normal local runs brittle.

### Out of scope

- Mandatory optional-scanner presence for local development
- Security-tool orchestration beyond normalized finding import

---

## Phase 9: Optional LangGraph Boundary Proof

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

- [ ] LangGraph remains optional and isolated behind an extra.
- [ ] The native runtime remains the primary execution path.
- [ ] Shared policy and audit invariants still hold for the covered path.

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
