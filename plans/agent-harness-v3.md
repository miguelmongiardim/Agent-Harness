# Plan: Agent Harness V3

> Source comparison: local ignored `deep-research-report.md`, V2 release state
> in [plans/agent-harness-v2.md](agent-harness-v2.md), and the public roadmap.

## Planning Decision

V3 should focus on operational integration hardening.

V2 closed the core control plane: public V2 schemas, non-widening migration,
policy-gated context and provider input, approval-bound provider execution,
redacted provider-call evidence, advisory scanner artifacts, local retrieval
fixtures, V2 templates, benchmark adapter evidence, docs checks, and release
readiness.

The deep-research report still points to several gaps that matter before web UI,
autonomous multi-agent orchestration, or broad platform claims:

- live provider adapters beyond recorded fixtures
- executable security and SBOM tools rather than passive report discovery
- configurable audit retention and redacted/non-redacted logging modes
- trace correlation and operational metrics
- production local Qdrant server mode without remote embeddings
- a sandboxed MCP boundary behind explicit capabilities
- additional templates such as `docs-rag`, `.NET service`, and embedded C/C++
- reproducible local packaging through Docker and pre-commit hooks

V3 should therefore build the next layer of operational evidence while
preserving V2 invariants: native runtime first, policy as the permission
ceiling, no raw provider payloads by default, local-first reproducibility, and
no roadmap claims without tests.

## V2 Coverage From The Research Report

- Explicit task, policy, template, and config contracts exist as public V2
  schemas.
- Context packs are explicit and include retrieval provenance, sensitivity, and
  policy evidence.
- Provider use, provider input, template apply, patch, and git commit mutations
  are approval-bound.
- Runs leave append-only events, artifacts, checkpoints, approvals, summaries,
  exports, and release-readiness evidence.
- Local benchmark samples exercise real run evidence instead of synthetic
  result reports.
- Docs checks gate unsupported claims, schema drift, links, and roadmap scope.

## Remaining Research Gaps

- Provider adapters are still recorded/local by default; live smoke execution
  exists only as an opt-in boundary.
- External security tools are advisory report inputs, not first-class
  policy-mediated tool adapters with generated artifacts.
- Audit retention profiles are not yet configurable as `dev`, `ci`, and
  `enterprise` policy behavior.
- Redacted and non-redacted logging modes are not selectable through a public
  policy contract.
- OpenTelemetry-style trace ids, spans, and exportable run correlations are not
  emitted.
- Dense retrieval is limited to deterministic local fixtures; production local
  Qdrant server mode is deliberately absent.
- MCP is represented as an adapter boundary only; no read-only resources or
  prompts flow through policy yet.
- Template breadth remains the Python trio; the research report also calls for
  `docs-rag`, `.NET service`, and embedded C/C++ starts.
- CI does not yet run Semgrep, Trivy, Gitleaks, CycloneDX generation, pre-commit,
  or SARIF upload as configurable evidence lanes.
- Docker packaging is absent.

## V3 Scope

### Phase 1: Live Provider Gateway Smoke Evidence

**Goal**: prove real provider calls can run only through the V2 provider,
policy, approval, and audit boundaries.

**Acceptance criteria**

- OpenAI-compatible live smoke is opt-in through environment variables and a
  pytest marker.
- Anthropic-compatible live smoke is represented as the same provider gateway
  contract or explicitly reported as unsupported.
- Live calls require provider-use approval unless the selected policy profile
  allows them.
- Provider-call artifacts keep raw payloads absent by default.
- Release evidence records whether live smoke was skipped, passed, or not
  configured.

### Phase 2: Security Tool Adapters And CI Evidence

**Goal**: turn external scanner evidence into policy-mediated adapters instead
of passive optional files.

**Acceptance criteria**

- Gitleaks, Semgrep, Trivy, and CycloneDX adapters can run when tools are
  installed and report clear missing-tool warnings otherwise.
- Policy controls which scanners are advisory and which are blocking.
- Generated scanner outputs are recorded as run or release artifacts.
- SARIF export includes first-party and external scanner findings.
- CI has optional lanes for scanner execution and SARIF upload without breaking
  default local workflows.

### Phase 3: Audit Retention And Logging Modes

**Goal**: make retention and logging behavior explicit policy, not implicit
artifact cleanup.

**Acceptance criteria**

- Public policy supports `dev`, `ci`, and `enterprise` retention profiles.
- Retention reports explain what would be retained or pruned before mutation.
- Redacted logging remains the default.
- Non-redacted logging requires an explicit named profile and approval gate.
- Retention behavior is covered by tests without deleting unrelated user files.

### Phase 4: Observability And Trace Correlation

**Goal**: expose operational metrics and trace ids across runs, provider calls,
tools, approvals, retrieval, exports, and benchmarks.

**Acceptance criteria**

- Runs emit stable trace ids and span-like records without requiring a remote
  collector.
- Provider calls, tool calls, retrieval, approvals, exports, and benchmark
  results reference trace ids.
- Metrics include latency, approval rate, tool success rate, reproducibility
  evidence, and audit completeness.
- OpenTelemetry export is optional and fails closed when the dependency is
  missing.

### Phase 5: Retrieval Backend Hardening

**Goal**: promote local Qdrant server mode from future scope into a tested,
policy-visible backend while keeping remote embeddings out of scope.

**Acceptance criteria**

- Local Qdrant server mode is explicitly configured and never inferred.
- Embedding behavior remains local-only.
- Context manifests record server mode, collection/index id, embedding model,
  chunk ids, scores, fallback reason, and policy evidence.
- Missing server or dependency failures fall back or fail according to policy.
- Benchmarks include one server-mode retrieval case without claiming public
  benchmark comparability.

### Phase 6: Template Expansion And Catalog Hygiene

**Goal**: add one high-value non-runtime template slice before broad catalog
work.

**Acceptance criteria**

- Add a `docs-rag` V2 template with policy, retrieval, eval, and demo metadata.
- Validate template compatibility before write planning.
- Keep `.NET service` and embedded C/C++ as later candidates unless explicitly
  promoted.
- Template docs separate bundled templates from future external catalogs.

### Phase 7: MCP Read-Only Adapter Boundary

**Goal**: prove MCP can expose resources and prompts as untrusted, policy-filtered
context without becoming the runtime trust boundary.

**Acceptance criteria**

- MCP support is behind an explicit capability flag and optional dependency.
- Read-only resources can be imported into context manifests with sensitivity
  and provenance.
- MCP prompts are treated as untrusted templates or evidence, not authority.
- MCP tool execution remains out of scope unless separately approved.
- Adversarial tests cover resource injection and capability bypass attempts.

### Phase 8: V3 Docs, Packaging, And Release Evidence

**Goal**: close V3 with public docs and release gates that match implemented
behavior.

**Acceptance criteria**

- README, architecture, security, retrieval, templates, MCP, observability, and
  release docs describe only implemented V3 behavior.
- `CHANGELOG.md` has a V3 entry.
- Release readiness records local checks, docs checks, CI matrix, scanner lanes,
  live-smoke status, and tag evidence.
- Dockerfile and pre-commit setup exist if they were implemented in V3, or stay
  explicitly deferred.

## Deferred Beyond V3

- Web API and approval UI.
- Autonomous or collaborative multi-agent orchestration.
- External template catalogs and remote template discovery.
- Enterprise identity, centralized secrets management, hardened sandboxing,
  attestation, and compliance readiness claims.
- Full SWE-bench or Terminal-Bench dataset execution and leaderboard-style
  comparability claims.
- Remote embeddings.

## First Next Step

Write the V3 PRD from this plan, then start Phase 1 with a RED test proving a
live-provider smoke run cannot execute unless the provider-use approval binding
matches the selected live provider profile, trust zone, model id, input hash,
policy decision id, and checkpoint hash.
