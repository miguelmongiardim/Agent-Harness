# PRD: Agent Harness V1

## Problem Statement

Agent Harness V0 proves a local, policy-gated software-engineering workflow
with deterministic mock execution, inspectable artifacts, approval-bound patch
flow, provenance-aware retrieval, evals, and exports. That is enough to prove
the core runtime shape, but it is not yet enough to support the main product
goal described in [deep-research-report.md](/C:/Users/mmarque9/agent_harness/deep-research-report.md):
controlled real-provider execution for software-engineering workflows without
giving up approval gates, trust boundaries, data controls, auditability, or
reproducibility.

That gap matters for three groups:

- developers who want to test real provider-backed workflows rather than only a
  deterministic mock
- reviewers who need explicit evidence of what crossed policy, trust, and
  approval boundaries
- security and governance stakeholders who need strong controls over provider
  use, retrieved context, sensitive data handling, and high-risk git actions

Without V1, Agent Harness remains a credible V0 proof but not yet a credible
runtime for controlled provider-backed engineering workflows. The short
[docs/roadmap.md](/C:/Users/mmarque9/agent_harness/docs/roadmap.md) also
compresses V1 too aggressively, so V1 needs a stronger product boundary than a
few roadmap bullets.

## Solution

Agent Harness V1 extends the existing CLI-first, local-first runtime so users
can run tasks against named provider profiles defined in project config, while
keeping policy mediation and auditability as the system's primary identity.

From a user perspective, the workflow is:

- choose or inherit a configured provider profile
- let policy evaluate provider use based on explicit `trust_zone`, sensitivity
  class, and network status
- assemble provider-bound context only from policy-approved evidence
- record included and rejected evidence with provenance, sensitivity, and
  policy decisions
- pause for approval when provider use or high-risk mutation requires it
- allow separate `git_commit` approval only after approved patches are applied
  and required checks pass
- inspect run artifacts that show exactly what happened, what was blocked, and
  why

V1 also broadens the harness around that core:

- hybrid lexical+dense retrieval with transparent provenance
- richer public sensitivity classes and provider-input policy
- a packaged template registry over in-repo bundles
- benchmark-shaped sample packs rather than full benchmark infrastructure
- normalized scanner findings with graded policy thresholds
- optional LangGraph boundary proof without replacing the native runtime

V1 deliberately avoids:

- implicit trust based on endpoint URL or localhost
- inline secrets or secret values in artifacts
- arbitrary provider definitions from the CLI
- remote embeddings in the default path
- unrestricted git operations
- benchmark-scale dataset infrastructure
- UI-first expansion or framework lock-in

## User Stories

1. As a developer, I want to select a configured provider profile for a task run,
   so that provider-backed execution is reproducible and policy-bounded.
2. As a reviewer, I want provider trust zones to be explicit, so that local
   services, private-network services, and hosted providers are not treated as
   equivalent.
3. As a security reviewer, I want provider-bound context filtered by
   sensitivity class and provider-input policy, so that denied data never
   leaves Agent Harness.
4. As a developer, I want lexical and dense retrieval to both contribute to
   context, so that exact symbol lookup and semantic recall both work.
5. As a reviewer, I want included and rejected context items to be inspectable
   with provenance and policy evidence, so that I can audit why each item did
   or did not enter a context pack.
6. As a maintainer, I want provider credentials referenced only through allowed
   environment variable names, so that secrets are never stored in configs,
   task specs, templates, or run artifacts.
7. As a reviewer, I want `git_commit` to require a separate approval with an
   exact final message binding, so that patch approval and commit approval
   remain distinct.
8. As a maintainer, I want template discovery and application to run through a
   packaged registry and approval-bound writes, so that scaffolding remains
   reusable and auditable.
9. As a maintainer, I want benchmark-shaped sample packs for issue-style and
   terminal-style tasks, so that V1 demonstrates benchmark integration without
   depending on large public datasets.
10. As a security reviewer, I want normalized security findings and graded
    scanner thresholds, so that risky runs fail early but optional tools do not
    make normal local runs brittle.
11. As a contributor, I want provider integrations validated offline by default
    and through opt-in live smoke tests only when explicitly enabled, so that
    CI stays deterministic and credential-free.
12. As an experimenter, I want an optional LangGraph-backed audited run, so
    that boundary compatibility can be proven without making LangGraph the core
    runtime.

## Behavioral Requirements

1. A user can define V2 provider profiles in project config with required
   fields `provider_profile_id`, `transport`, `trust_zone`, `model`,
   `endpoint_env`, `network`, and `requires_approval`, plus optional
   `api_key_env`.
2. A task can select one configured provider profile by id, and if it does not,
   the runtime uses the configured project default profile.
3. CLI overrides can switch only to another configured provider profile and
   cannot invent or override provider endpoints, models, transports, or trust
   zones directly.
4. The runtime records `provider_profile_id`, `transport`, `trust_zone`,
   `model`, endpoint identity, network flag, and approval id in run metadata.
5. Provider trust is never inferred from endpoint URL. `localhost` is not
   automatically trusted.
6. In the default trust-zone policy, `mock` is allowed, `local_process` is
   allowed only when no network boundary exists, and `local_endpoint`,
   `private_network`, and `hosted_provider` require approval before provider
   use.
7. All provider calls are audited regardless of trust zone.
8. Provider profiles may reference credentials only through env-var names, and
   the runtime fails with a clear error when a required env var is missing.
9. Secret values never appear in task specs, checked-in config, templates, run
   artifacts, or audit logs.
10. Policy can restrict which env-var names are allowed for each provider
    profile.
11. Public sensitivity classes in V1 are `public`, `internal`,
    `confidential`, `restricted`, `secret`, `pii`, `customer`, `credential`,
    `generated`, and `unknown`.
12. Unlabeled repo files default to `internal`, `generated` content is treated
    as untrusted evidence, and `unknown` defaults to denied.
13. Provider-input policy supports actions `allow`, `allow_untrusted`,
    `approval_required`, `redact`, and `deny`.
14. In the default provider-input policy:
    `public` is allowed,
    `generated` is allowed only as untrusted evidence,
    `internal` requires explicit provider-input approval,
    and `confidential`, `restricted`, `secret`, `credential`, `pii`,
    `customer`, and `unknown` are denied.
15. `secret`, `credential`, `pii`, and `customer` are hard-denied in the
    default policy and cannot be overridden by normal run approval.
16. Task specs and CLI flags can narrow provider-input permissions but cannot
    widen the active policy ceiling.
17. If a provider-input rule uses `redact`, redaction occurs before
    provider-bound context assembly, then the item is reclassified and
    reevaluated before inclusion.
18. Every provider-bound context item records sensitivity class, policy
    decision, redaction status, trust zone, and approval id if applicable.
19. Hybrid retrieval runs lexical retrieval and dense retrieval as first-class
    sources, normalizes results into a shared retrieved-item model,
    deduplicates them, and records whether an included item came from lexical,
    dense, or both.
20. Dense retrieval uses local embeddings by default, and the context manifest
    records embedding backend and embedding model/version.
21. `context_manifest.v2` records included and rejected items explicitly, and
    each item records source kind, path or chunk id, sensitivity class,
    retrieval method, provenance, policy action, policy reason, and policy
    decision id.
22. `secret`, `credential`, `pii`, and `customer` are denied from context
    packs in the default profile.
23. `agent-harness template list` and `agent-harness template show` read from a
    packaged registry, and `agent-harness template apply` validates
    compatibility before approval-bound writes.
24. Applied templates record template id and version in workspace metadata.
25. `git_commit` becomes available only after approved patches are applied and
    required tests or success checks pass.
26. The runtime may propose a commit message based on the approved diff and run
    summary, but no model-generated commit message may be committed without
    human approval.
27. The human reviewer may edit the proposed commit message before approval,
    and once approved the final message is immutable for that approval record.
28. `git_commit` approval is denied if the final message, parent HEAD, exact
    file set, content hashes, diff hash, policy profile, or checkpoint hash no
    longer match the approval binding at execution time.
29. `git_commit` stages only the exact approved file set and never performs
    push, branch switching, rebase, broad staging, or inclusion of unapproved
    files.
30. V1 benchmark adapters can import local SWE-bench-style and terminal-task
    sample packs into task, workspace, policy, eval, and export flows without
    large external downloads.
31. Pre-run scanner gates normalize findings into a shared security-finding
    model, apply policy fail thresholds, and block runs when required findings
    exceed the configured threshold.
32. Optional live provider tests run only when explicitly enabled and do not
    gate normal credential-free CI.
33. An optional LangGraph extra can execute one minimal audited run through the
    same policy, approval, and audit boundaries as the native runtime.

## Implementation Decisions

- **Core system boundary**: V1 remains CLI-first and local-first. It extends
  the current runtime rather than replacing it with a different execution
  framework.
- **Source of truth**: [deep-research-report.md](/C:/Users/mmarque9/agent_harness/deep-research-report.md)
  is the conceptual anchor for V1. The short roadmap should be updated to match
  this PRD after acceptance.
- **Schema strategy**: materially changed public models move to `v2` while
  loaders remain backward-compatible with V0/V1 files where practical.
- **Provider profile boundary**: provider selection lives in project config as
  named provider profiles. The public contract separates `transport` from
  `trust_zone`.
- **Transport decisions**: V1 supports `mock`, `openai_compatible`, and
  `anthropic` transports. Local-compatible endpoints use
  `openai_compatible` transport with an explicit `trust_zone`; V1 does not add
  a separate `local_compatible` provider type.
- **Trust-zone policy**: allowed trust zones are `mock`, `local_process`,
  `local_endpoint`, `private_network`, and `hosted_provider`. Policy evaluates
  trust-zone behavior explicitly; endpoint URLs never determine trust.
- **Credential boundary**: provider profiles store only env-var names for
  secrets. Secret values are resolved at execution time and never persisted in
  task specs, checked-in config, templates, run artifacts, or audit logs.
- **Sensitivity model**: V1 promotes the richer public sensitivity classes and
  treats classification as a first-class field in policy, manifests, audit, and
  provider-input decisions. V0 aliases may be supported only for migration.
- **Provider-input policy ceiling**: policy profiles define the maximum allowed
  provider-input behavior by sensitivity class. Task specs and CLI flags cannot
  widen that ceiling.
- **Default provider-input matrix**: the default profile is intentionally
  strict:
  `public: allow`,
  `generated: allow_untrusted`,
  `internal: approval_required`,
  `confidential: deny`,
  `restricted: deny`,
  `secret: deny`,
  `credential: deny`,
  `pii: deny`,
  `customer: deny`,
  `unknown: deny`.
- **Looser profiles**: any profile looser than the default must be explicit,
  named, documented, and deliberately selected. Any relaxation for
  `restricted` must be explicitly local-only.
- **Retrieval architecture**: lexical and dense retrieval remain co-equal
  sources in a fixed hybrid pipeline: retrieve, normalize, filter, deduplicate,
  rank or merge, then emit provenance.
- **Embedding policy**: dense retrieval uses local embeddings by default.
  Remote embeddings are out of the default V1 path and require a future
  explicit policy-approved adapter.
- **Context manifest model**: `context_manifest.v2` includes both included and
  rejected items as first-class evidence so reviewers can inspect not only what
  entered context but also what was blocked and why.
- **Deep modules**: the main V1 deep modules are the provider gateway,
  trust-zone and provider-input policy evaluator, hybrid retrieval coordinator,
  context-manifest builder, template registry, benchmark-pack adapter,
  security-finding normalizer, and commit-approval binder.
- **Template catalog**: template bundles remain in-repo, but discovery uses a
  packaged read-only SQLite registry with metadata for validation,
  compatibility, versioning, and future extension.
- **Bundled templates**: V1 bundles `python-lib`, `fastapi-service`,
  `cli-tool`, `docs-rag`, `dotnet-service`, and `embedded-cpp`.
- **Benchmark scope**: V1 supports benchmark-shaped execution through local
  sample packs only. Full public dataset ingestion and large-scale benchmark
  execution are deferred.
- **Scanner scope**: scanner outputs normalize into a common
  `SecurityFinding` model with graded thresholds. Required first-party checks
  always run. Optional external tools are used when available.
- **Git mutation boundary**: `git_commit` is a separate high-risk tool. Patch
  approval never implies commit approval, and commit execution is bound to the
  exact approved repository state plus the final approved message hash.
- **Framework adapters**: the native runtime remains primary. LangGraph support
  is an optional boundary-proof extra, not a new core runtime identity.

## Testing Decisions

- Good V1 tests verify public behavior through CLI commands, runtime entry
  points, manifests, approval artifacts, exports, and benchmark or scanner
  outputs rather than private implementation details.
- Highest-risk behaviors are:
  provider trust-zone handling,
  provider-input policy enforcement,
  hard-denied class handling,
  redaction and reclassification,
  provider secret handling,
  hybrid retrieval provenance,
  and `git_commit` approval binding.
- Unit tests should cover:
  V2 schema validation,
  trust-zone policy evaluation,
  provider-input matrix evaluation,
  env-var restriction logic,
  sensitivity-class defaults,
  redaction behavior,
  approval-binding validation,
  and security-finding normalization.
- Integration tests should cover:
  provider-profile selection,
  run metadata recording,
  provider-bound context assembly,
  hybrid retrieval manifest generation,
  template registry discovery and apply,
  benchmark sample-pack execution,
  scanner gating,
  and inspect/export surfaces.
- Adversarial or regression tests should cover:
  localhost being treated as safe,
  denied sensitivity classes leaking into provider input or context packs,
  prompt injection in retrieved docs,
  secret leakage into logs or artifacts,
  stale commit approvals,
  message-hash drift,
  and task/CLI attempts to widen policy.
- Provider integration testing should default to:
  deterministic unit tests,
  mock-provider tests,
  recorded fixture tests,
  and optional live smoke tests only when explicitly enabled.
- Normal CI must not require provider credentials and must not make outbound
  model calls.
- V1 acceptance is defined by externally observable behavior across provider
  selection, provider-input filtering, retrieval provenance, approval flow,
  template application, scanner gating, benchmark-shaped execution, and audit
  evidence.

## Out of Scope

- Inline config secrets or secret backends.
- Remote embeddings in the default V1 retrieval path.
- Arbitrary provider, model, endpoint, or trust-zone definition at runtime.
- Full benchmark dataset ingestion or benchmark-scale execution.
- Push, branch switching, rebase, or broad git staging.
- Raw provider payload capture by default.
- External template catalogs in V1.
- Mandatory optional-scanner availability for normal local runs.
- Web API, web UI, approval dashboard, MCP-centric architecture, multi-agent
  execution, or full LangGraph parity.

## Further Notes

- V1 should be implemented as vertical slices on top of the completed V0 base,
  not as a horizontal rewrite.
- The main product risk is policy erosion while adding real provider support.
  V1 should bias toward explicit permission ceilings, approval checkpoints, and
  audit-first behavior.
- The public docs should define each sensitivity class clearly and explain the
  difference between untrusted generated evidence, denied unknown inputs, and
  hard-denied sensitive classes.
- The roadmap should be realigned after this PRD is accepted so the public V1
  description matches the actual delivery boundary.
