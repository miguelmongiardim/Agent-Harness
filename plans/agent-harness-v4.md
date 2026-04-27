# Plan: Agent Harness V4 Provider Core

> Source PRD: [docs/prd-agent-harness-v4.md](../docs/prd-agent-harness-v4.md)

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: preserve `run`, `approve`, `inspect run`, `eval`, and
  `docs check`; add no new provider command in V4.
- **Key models**: add `provider_action_envelope.v1` as the only provider-output
  shape that can enter runtime action planning.
- **Schema**: extend provider artifact schemas for envelope hashes, checkpoint
  binding, and redacted prompt/response artifact references.
- **Storage**: store inspectable redacted artifacts and hashes, not raw provider
  request bodies, response bodies, credentials, or sensitive payloads.
- **Runtime boundary**: provider adapters return validated envelopes and
  provider-call evidence; tool execution remains owned by the native runtime and
  policy engine.
- **Policy boundary**: existing provider-use, provider-input, trust-zone, and
  tool policies remain the permission ceiling.
- **Approval model**: provider-use approval remains checkpoint-bound and
  provider-input-bound; live smoke requires approval unless a test/demo path
  explicitly auto-approves.
- **Audit model**: provider-call evidence links provider profile, trust zone,
  mode, approval ids, provider-input hash, action-envelope hash, checkpoint
  hash, redacted artifact refs, latency, and token metrics when available.
- **External service boundary**: OpenAI-compatible live smoke is the only V4
  live provider path and is disabled unless explicit opt-in and credentials are
  present.

---

## Phase 0: V4 Provider-Core Scope Docs

**User stories covered**

- Story 2: reviewer can understand the audit boundary.
- Story 4: contributor can distinguish deterministic CI from live smoke.
- Story 5: operator can see live smoke is optional.

**Observable behaviors**

- Public docs identify V4 Provider Core as the next implementation boundary.
- Roadmap links the V4 PRD and plan.
- Docs keep deferred work clearly out of scope.

**First RED test**

- `agent-harness docs check` or a focused docs guard fails until V4
  provider-core scope is documented without unsupported capability claims.

### What to build

Write the durable V4 PRD and vertical-slice plan. Update roadmap references so
the next track points at Provider Core specifically, not the broader
conception-alignment draft.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v4.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v4.md` is a vertical-slice provider-core plan.
- [x] `docs/roadmap.md` points to the V4 provider-core PRD and plan.
- [x] Fixture capture, API/UI, MCP, multi-agent workflows, retention profiles,
      retrieval redesign, and enterprise claims are explicitly out of scope.
- [x] Docs check passes.

### Out of scope

- Runtime implementation.
- New provider commands.
- Fixture capture tooling.

---

## Phase 1: Provider Output Rejected Before Tool Execution

**User stories covered**

- Story 3: malformed or unsafe provider output is rejected before tools run.
- Story 4: deterministic provider paths exercise the same boundary.

**Observable behaviors**

- A recorded provider response with invalid JSON, malformed envelope shape,
  unknown tool names, invalid arguments, refusal, or unsupported action fails
  before tool execution.
- The run records failure evidence in events and provider artifacts.
- Mock and recorded-fixture paths use the same validation boundary.

**First RED test**

- A recorded provider fixture containing malformed provider output reaches
  runtime action planning or tool execution instead of failing with a typed
  provider-envelope validation error.

### What to build

Introduce `provider_action_envelope.v1` as the provider-output boundary. Route
mock and recorded-fixture responses through the same validator before the
runtime receives tool calls. Write failure evidence without executing proposed
tools.

### Acceptance criteria

- [ ] `provider_action_envelope.v1` validates action lists, refusals, and
      unsupported responses strictly.
- [ ] Unknown tool names and invalid tool arguments fail before policy/tool
      execution.
- [ ] Mock and recorded-fixture provider paths both return validated envelopes.
- [ ] Provider adapters cannot return direct tool calls to the runtime.
- [ ] Invalid provider output writes an event and provider artifact explaining
      the sanitized failure.

### Out of scope

- Live provider network calls.
- Redacted prompt/response artifact expansion beyond failure evidence needed for
  this slice.

---

## Phase 2: Provider Profile Validation Protects Live Setup

**User stories covered**

- Story 1: configured providers can participate only through valid profiles.
- Story 3: unsafe provider configuration fails before provider use.
- Story 5: optional live setup has clear skip/failure behavior.

**Observable behaviors**

- Incomplete or unsafe provider profiles fail with actionable diagnostics before
  provider use.
- Diagnostics name missing or invalid env var names but never print env var
  values.
- Existing provider approval and provider-input policies remain the ceiling.

**First RED test**

- An unsafe or incomplete OpenAI-compatible provider profile is accepted until
  execution fails with an unclear transport error or leaks config details.

### What to build

Add pre-provider-use profile validation for endpoint env, API-key env,
transport, trust zone, network flag, live opt-in, and approval requirements.
Ensure validation happens before provider calls and before any credential value
can enter artifacts.

### Acceptance criteria

- [ ] Profile validation covers endpoint env, API-key env, transport, trust
      zone, network flag, and live opt-in requirements.
- [ ] Diagnostics mention env var names and never include env var values.
- [ ] OpenAI-compatible live profiles require approval-compatible policy.
- [ ] Provider-input and provider-use policy checks still run and cannot be
      widened by profile settings.

### Out of scope

- New profile management CLI.
- Anthropic live profile support.

---

## Phase 3: Opt-In OpenAI-Compatible Smoke Completes Safely

**User stories covered**

- Story 1: configured provider can participate in a controlled run.
- Story 2: reviewer can inspect approval and provider-call evidence.
- Story 5: live tests skip when credentials are missing.

**Observable behaviors**

- A live OpenAI-compatible provider can complete a minimal public read-only task
  only when explicit opt-in, credentials, profile, policy allowance, and
  provider-use approval are present.
- Missing opt-in or credentials skip live tests and do not fail normal CI.
- The smoke task uses public or synthetic context only.

**First RED test**

- A live OpenAI-compatible provider cannot complete a minimal public read-only
  task under explicit opt-in and approval, or attempts to run in normal CI.

### What to build

Implement the narrow OpenAI-compatible live smoke path behind the existing
provider gateway and runtime approval flow. Use the same action envelope,
provider-input, approval, and artifact boundaries as deterministic paths.

### Acceptance criteria

- [ ] Live smoke requires explicit env opt-in.
- [ ] Missing live credentials skip live tests.
- [ ] Provider use pauses for approval unless explicitly auto-approved in a
      controlled test/demo path.
- [ ] Smoke task uses only public or synthetic context.
- [ ] Normal CI does not run live calls.
- [ ] Raw credentials and raw provider payloads are absent from artifacts.

### Out of scope

- General live-provider benchmark suite.
- Production provider reliability guarantees.
- Anthropic live support.

---

## Phase 4: Provider Evidence Links Inputs, Envelope, And Redaction

**User stories covered**

- Story 2: reviewer can audit provider-call evidence.
- Story 3: unsafe output failures remain inspectable.
- Story 4: deterministic paths prove artifact behavior.

**Observable behaviors**

- `provider_calls.json` binds approval ids, provider-input hash,
  action-envelope hash, checkpoint hash, mode, latency, and token metrics when
  available.
- Redacted prompt and response artifacts are referenced from provider-call
  evidence.
- Hard-denied data, raw credentials, private data, and sensitive payloads are
  absent from provider artifacts.

**First RED test**

- Provider-call evidence lacks approval linkage, provider-input binding,
  action-envelope hash, checkpoint hash, or redacted prompt/response artifact
  references.

### What to build

Extend provider-call evidence and artifact indexing so each provider call can be
audited without raw payload storage. Write redacted prompt artifacts from
allowed or redacted provider-input records and redacted response artifacts from
validated envelopes or sanitized provider errors.

### Acceptance criteria

- [ ] Provider-call artifacts include approval ids, provider-input hash,
      action-envelope hash, checkpoint hash, mode, latency, and token metrics
      when available.
- [ ] Redacted prompt artifact contains only allowed or redacted provider-input
      records.
- [ ] Redacted response artifact contains the validated envelope or sanitized
      error evidence.
- [ ] Artifact index references provider-call evidence and redacted artifacts.
- [ ] Secret values, raw credentials, private data, hard-denied data, and
      sensitive payloads are absent from artifacts.

### Out of scope

- Retention profile design.
- Raw provider payload archival.

---

## Phase 5: Provider-Core Evals And Setup Docs

**User stories covered**

- Story 2: reviewers can verify provider-core behavior through eval evidence.
- Story 4: contributors have deterministic provider tests.
- Story 5: operators understand optional live smoke behavior.

**Observable behaviors**

- `agent-harness eval` proves provider-core behavior through mock and recorded
  deterministic paths.
- Docs explain provider setup, safety boundaries, fixture expectations, live
  smoke, and unsupported roadmap items.
- Optional live smoke remains credential-gated and skipped by default.

**First RED test**

- `agent-harness eval` does not prove provider-core behavior through
  deterministic paths.

### What to build

Add eval scenarios for provider-core invariants and update setup/safety docs.
Include integration and adversarial coverage for recorded OpenAI-compatible
provider runs, inspect output, provider evidence, redacted artifacts, malformed
output, unauthorized tool actions, provider-input hard-deny leakage, and
approval drift.

### Acceptance criteria

- [ ] Eval scenarios cover mock and recorded-fixture provider paths.
- [ ] Integration coverage proves recorded OpenAI-compatible provider run,
      inspect output, provider evidence, and redacted artifacts.
- [ ] Adversarial coverage proves malformed provider output, unauthorized tool
      action, provider-input hard-deny leakage, and approval drift fail safely.
- [ ] Optional live OpenAI-compatible smoke skips unless env opt-in and
      credentials exist.
- [ ] Provider setup and safety-boundary docs pass `agent-harness docs check`.
- [ ] Docs state that fixture capture, API/UI, MCP, multi-agent workflows,
      retention profiles, retrieval redesign, Anthropic live support, and
      enterprise claims are outside V4.

### Out of scope

- Full public benchmark datasets.
- Fixture capture/replay commands.
- UI or hosted operator surfaces.

## Cross-Phase Invariants

- Policy remains the permission ceiling.
- Provider input is built from the context manifest, not ad hoc prompt assembly.
- Provider output is untrusted until schema-validated.
- Provider adapters cannot execute tools.
- Network access is denied by default.
- Live execution is opt-in and approval-bound.
- Approval records remain inspectable and checkpoint-bound.
- Raw secrets, credentials, PII, customer data, hard-denied data, and raw
  provider payloads are not stored.
- Recorded fixtures remain the normal deterministic test path.
- Tests verify public CLI/runtime/provider-gateway behavior, not private helper
  internals.
- Public docs keep implemented behavior separate from roadmap items.

## TDD Execution Rules

- Choose one observable behavior per slice.
- Write one failing public-interface test first.
- Implement the minimum code needed for green.
- Refactor only after tests are green.
- Do not add horizontal infrastructure unless the current or next slice
  exercises it.
- Do not implement roadmap features without an observable behavior and
  acceptance test.

## Later Tracks

- V5: retrieval hardening, optional production-grade retrieval paths, and
  retrieval quality metrics.
- V6: local web API and approval/inspection UI over existing artifacts.
- V7: read-only MCP resources/prompts, then separately gated MCP tool execution.
- V8: supply-chain and governance hardening with stronger scanner/SBOM evidence,
  `SECURITY.md`, Dependabot, docs build workflow, and retention reporting.
- V9: policy-mediated multi-agent orchestration only after single-agent live
  provider execution is safe and measurable.
