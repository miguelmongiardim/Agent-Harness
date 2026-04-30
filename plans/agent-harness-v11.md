# Plan: Agent Harness V11 Policy-Mediated Multi-Agent Orchestration

> Source PRD: [docs/prd-agent-harness-v11.md](../docs/prd-agent-harness-v11.md)

V11 targets `v1.7.0`. This plan is intentionally sliced around observable
policy-mediated orchestration behavior. Implementation should follow the
PRD -> Plan -> TDD workflow and proceed one public behavior at a time. Do not
build horizontal orchestration infrastructure unless a phase exercises it
through a user-visible behavior.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness orchestration run`, `inspect`,
  `export`, `approve`, and `resume`. Keep `agent-harness run` focused on one
  `task.v2` child task.
- **Key models**: add `orchestration.v1`, orchestration summary, child record,
  handoff record, orchestration event, orchestration artifact index, and
  orchestration-plan approval binding models under the orchestration boundary.
- **Schema**: extend `policy.v2` with an explicit `orchestration` section.
  Missing section denies orchestration but remains valid for single-agent runs.
  Add generated orchestration handoff context in a compatible context-manifest
  path.
- **Storage**: store aggregate evidence under
  `.agent-harness/orchestrations/<orchestration-id>/`; keep child run evidence
  under `.agent-harness/runs/<run-id>/`.
- **Runtime boundary**: orchestration is a supervisor over the native
  `HarnessRuntime`; it is not a replacement runtime, LangGraph graph, or MCP
  execution path.
- **Policy boundary**: child authority is the intersection of selected policy,
  role ceiling, child declaration, task constraints, and path policy. A child
  never widens policy, provider, tool, path, or context authority.
- **Approval model**: add `orchestration_plan` approval for risky supervisor
  plans. Existing child-run approvals remain separate and exact-effect bound.
- **Audit model**: append orchestration events for validation, policy decisions,
  approvals, child lifecycle, handoffs, pause/resume, failure, and completion.
- **MCP boundary**: expose orchestration evidence as read-only MCP resources
  only. Do not add MCP tools, approval mutation, run execution, provider
  execution, or resume behavior.
- **External service boundary**: V11 is local and deterministic by default.
  Networked providers remain explicit child choices and use existing provider
  gates.

---

## Phase 0: V11 Scope Is Documented And Guarded

**User stories covered**

- Story 15: release maintainer can see the planned V11 acceptance path.
- Story 16: documentation reviewer can separate implemented V11 behavior from
  later multi-agent scope.
- Story 17: maintainer can place orchestration contracts in the post-V10
  boundary layout.

**Observable behaviors**

- V11 PRD and vertical plan exist.
- Capability docs continue to treat multi-agent orchestration as future work
  until implementation phases land.
- Docs checks guard against claims for parallel, hosted, nested, MCP-execution,
  or enterprise multi-agent behavior outside roadmap/future language.

**First RED test**

- Add a docs-check test that fails if current capability docs claim parallel,
  hosted, nested, MCP-execution, or enterprise multi-agent behavior as current
  Agent Harness support.

### What to build

Add V11 PRD and plan, then extend docs-check claim guards only enough to keep
public documentation honest while implementation proceeds. Do not add
orchestration CLI behavior in this phase.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v11.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v11.md` exists and uses vertical tracer-bullet
      phases.
- [x] Docs checks fail on unsupported multi-agent capability claims.
- [x] README and roadmap do not describe V11 orchestration as implemented until
      code and release evidence exist.
- [x] No runtime, policy, storage, MCP, or CLI implementation is added in this
      phase beyond documentation guards.

### Phase 0 implementation notes

- Added `unsupported_orchestration_scope_claim` docs-check coverage for current
  docs that claim parallel, hosted, nested, MCP-execution, or enterprise
  multi-agent orchestration behavior.
- README and roadmap now link the V11 PRD and plan only as future local,
  sequential, policy-mediated orchestration scope.
- No orchestration runtime, policy, storage, MCP, release-readiness, or CLI
  implementation was added.

### Out of scope

- Orchestration schemas.
- CLI commands.
- Storage, runtime, MCP, or release-readiness implementation.

---

## Phase 1: Missing Orchestration Policy Denies Execution

**User stories covered**

- Story 4: policy author must explicitly enable orchestration.
- Story 6: child authority cannot bypass selected policy.
- Story 16: unsupported behavior is denied clearly.

**Observable behaviors**

- `agent-harness orchestration run <spec> --dry-run` parses a minimal
  `orchestration.v1` spec far enough to evaluate policy.
- A selected `policy.v2` profile without `orchestration` denies orchestration
  with a clear diagnostic.
- The denied command does not create child runs or mutation-capable artifacts.

**First RED test**

- An integration test invokes `agent-harness orchestration run minimal.json
  --dry-run` against the existing default policy and expects a nonzero exit,
  a clear missing-orchestration-policy message, and no child run directory.

### What to build

Add the smallest public path for orchestration command parsing, spec loading,
selected policy loading, and policy-section denial. Persist no aggregate
orchestration directory until policy allows the workflow.

### Acceptance criteria

- [x] The CLI command group exists with `run` help text.
- [x] Minimal `orchestration.v1` validation errors are actionable.
- [x] Missing `policy.v2.orchestration` denies orchestration.
- [x] Denial does not launch `HarnessRuntime`.
- [x] Existing `agent-harness run` behavior is unchanged.

### Phase 1 implementation notes

- Added a boundary-owned `agent_harness.orchestration` package with
  `orchestration.v1` spec loading and validation.
- Added `agent-harness orchestration run <spec> --dry-run` as a denial-first
  CLI path.
- The command loads the selected policy and fails before creating child runs or
  orchestration artifacts when `policy.v2.orchestration` is absent.
- Successful orchestration, child execution, role ceilings, handoffs, approvals,
  MCP resources, and release-readiness evidence remain out of scope.

### Out of scope

- Successful child execution.
- Role ceilings beyond enough schema to validate the denial path.
- Plan approval, handoffs, MCP resources, and release gates.

---

## Phase 2: User Can Run And Inspect A Minimal Read-Only Orchestration

**User stories covered**

- Story 1: developer can define a local multi-agent workflow.
- Story 2: child declarations are materialized into normal task artifacts.
- Story 3: reviewer can inspect aggregate orchestration evidence.

**Observable behaviors**

- With explicit orchestration policy, a one-child planner orchestration runs in
  dry-run mode.
- The child is materialized as a generated `task.v2` file and launched through
  the native runtime.
- The orchestration writes summary, events, manifest, child task artifact, child
  run link, and artifact index.
- `agent-harness orchestration inspect <id>` returns the aggregate evidence
  without executing children.

**First RED test**

- An integration test seeds a policy with orchestration enabled, runs a
  one-child planner spec with `--dry-run`, then inspects the orchestration and
  asserts summary status, child role, child run id, materialized task path, and
  event count.

### What to build

Implement the walking skeleton for allowed orchestration: spec validation,
policy enablement, deterministic orchestration id, aggregate store, one child
materialization, native runtime delegation, summary writing, event writing, and
inspect output.

### Acceptance criteria

- [x] One planner child completes through `HarnessRuntime` in dry-run mode.
- [x] Child run artifacts are normal run artifacts under `.agent-harness/runs/`.
- [x] Aggregate orchestration artifacts live under `.agent-harness/orchestrations/`.
- [x] Inspect output references child artifacts without copying raw run content.
- [x] No provider, write, handoff, approval, MCP, or release behavior is needed
      for this phase.

### Phase 2 implementation notes

- Added explicit `policy.v2.orchestration` parsing with enabled sequential
  local orchestration policy.
- Added boundary-owned orchestration summary, event, manifest, and artifact
  index evidence under `.agent-harness/orchestrations/<orchestration-id>/`.
- Added `agent-harness orchestration run <spec> --dry-run` for exactly one
  read-only child in this phase, materializing that child as `task.v2` before
  delegating to `HarnessRuntime`.
- Added `agent-harness orchestration inspect <id>` to return aggregate evidence
  and child artifact references without loading raw child run content.
- Multiple children, dependencies, handoffs, risky approvals, resume behavior,
  provider-backed children, MCP resources, and release gates remain later V11
  phases.

### Out of scope

- Multiple children.
- Dependency handoffs.
- Risky plan approval.
- Resume behavior.
- MCP resources.

---

## Phase 3: Dependency Order Produces Policy-Mediated Generated Handoffs

**User stories covered**

- Story 3: reviewer can audit child relationships and handoffs.
- Story 11: downstream children receive dependency handoffs as generated
  context.
- Story 12: sensitive data does not leak through handoffs.

**Observable behaviors**

- A two-child orchestration runs children in deterministic dependency order.
- After the first child completes, the supervisor writes a deterministic handoff
  record from safe child evidence.
- The dependent child receives only direct dependency handoffs as generated,
  policy-mediated context.
- The downstream child context manifest records handoff provenance and policy
  decision ids.

**First RED test**

- An integration test runs planner -> reviewer and asserts the reviewer child
  context includes one generated handoff with orchestration id, upstream child
  id, upstream run id, sensitivity `generated`, and a policy decision id.

### What to build

Add deterministic DAG validation, dependency ordering, generated handoff
construction, generated context injection into child task context assembly, and
handoff evidence records. Keep handoff generation deterministic and provider-
free.

### Acceptance criteria

- [x] Dependency cycles are rejected with clear validation errors.
- [x] Children run in dependency order.
- [x] Handoffs are written under the orchestration artifact directory.
- [x] Downstream child context includes direct dependency handoffs only.
- [x] Handoffs exclude raw provider prompts, raw provider responses, secrets,
      credentials, and denied context text.

### Phase 3 implementation notes

- Added deterministic dependency ordering for `orchestration.v1` children and
  validation-time dependency-cycle rejection before policy or artifact work.
- Added generated `orchestration_handoff.v1` records under
  `.agent-harness/orchestrations/<id>/handoffs/` after upstream child
  completion.
- Added generated handoff context injection into downstream child runs via the
  native runtime and context builder, with sensitivity `generated` and policy
  decision provenance recorded in the downstream `context_manifest.v2`.
- Added aggregate inspect output for handoff records and artifact-index
  references without copying raw child run content.
- Handoffs are deterministic summaries from safe child metadata only; provider
  prompts, provider responses, secrets, credentials, and denied context text
  are not included.

### Out of scope

- Parallel dependency branches.
- Explicit non-dependency handoff routing.
- Provider-generated summaries.
- MCP handoff resources.

---

## Phase 4: Role Ceilings And Risky Plans Pause For Approval

**User stories covered**

- Story 5: fixed roles constrain child authority.
- Story 6: child authority is an intersection of policy, role, child, task, and
  path constraints.
- Story 7: risky plans pause before children start.
- Story 8: orchestration-plan approval is exact and resumable.
- Story 9: child mutation still uses child-run approvals.

**Observable behaviors**

- Planner, implementer, reviewer, and tester role ceilings are enforced.
- A child cannot use a tool excluded by its role even if the global policy
  allows the tool.
- A plan containing any write-capable child pauses for `orchestration_plan`
  approval before launching children.
- After approval, resume launches children and existing child-run patch approval
  behavior still applies.
- Tampered plan artifacts or changed policy cause resume to fail before child
  execution.

**First RED test**

- An integration test runs an implementer orchestration with `patch_file`,
  expects a paused orchestration-plan approval before any child run exists,
  approves it, resumes, and verifies the child dry-run records the normal
  patch-file approval instead of mutating files.

### What to build

Add role ceiling evaluation, effective child authority summaries, risky-plan
detection, orchestration-plan approval records, exact binding validation,
`orchestration approve`, and `orchestration resume` for supervisor approvals.

### Acceptance criteria

- [x] Role ceilings are enforced for all four V11 roles.
- [x] Effective authority records are inspectable in orchestration evidence.
- [x] Risky plans pause before any child starts.
- [x] Approved risky plans resume only when bindings still match.
- [x] Child patch approvals remain separate child-run approvals.
- [x] Multiple write-capable children may appear only under sequential execution;
      no more than one writer is active at a time.

### Phase 4 implementation notes

- Added fixed V11 role ceilings for planner, implementer, reviewer, and tester;
  child-declared tools outside the role ceiling are rejected before artifacts
  or child runs are created.
- Added effective child authority records to orchestration summaries and
  `orchestration_plan.v1` evidence.
- Added risky-plan detection for write-capable children and provider-declaring
  children; risky plans pause with `orchestration_plan` approval before any
  child task materialization or child run creation.
- Added `agent-harness orchestration approve` and `agent-harness orchestration
  resume` for supervisor approvals. Resume validates the approved binding
  against the stored plan, current spec, and current policy before launching
  children.
- Child mutation remains delegated to normal child runs. A resumed dry-run
  implementer that proposes `patch_file` records the existing child-run
  `patch_file` approval and leaves files unchanged.
- Execution remains deterministic and sequential, so write-capable children do
  not overlap.

### Out of scope

- Git commit automation across child runs.
- Parallel writer scheduling.
- Operator UI approvals.

---

## Phase 5: Child Pause, Failure, And Explicit Provider Use Are Controlled

**User stories covered**

- Story 10: provider-backed children require explicit child declaration.
- Story 12: provider evidence does not leak through handoffs.
- Story 13: paused or failed children stop the orchestration deliberately.

**Observable behaviors**

- A child uses a provider only when its child declaration names a provider
  profile.
- Project default provider profiles are not inherited by orchestration children.
- Provider-backed children still pause for provider-use or provider-input
  approvals according to existing policy.
- If any child pauses or fails, the supervisor stops scheduling later children
  and records the blocked child.
- Resuming the orchestration after child-run approval continues from the next
  eligible child without rerunning completed children.

**First RED test**

- An integration test configures a default provider profile, runs an
  orchestration child without `provider_profile`, and asserts no provider
  artifact exists for that child. A second spec with explicit provider profile
  pauses or records provider evidence according to the existing provider gates.

### What to build

Thread explicit provider selection through child task materialization, block
provider default inheritance, propagate child paused/failed status to the
orchestration summary, and support resume after child-run approvals complete.

### Acceptance criteria

- [x] Provider default inheritance attempts are denied or ignored safely.
- [x] Explicit provider child runs use existing provider gates and artifacts.
- [x] Child pause stops the supervisor and marks the blocked child.
- [x] Child failure stops downstream scheduling.
- [x] Resume does not rerun completed children.
- [x] Handoffs and aggregate evidence never include raw provider payloads;
      orchestration export is covered by Phase 6.

### Phase 5 implementation notes

- Orchestration child runs now opt out of project default provider inheritance;
  a provider is used only when the child declaration names `provider_profile`.
- Explicit provider children still use normal provider profile validation,
  provider-use approval, provider-input evidence, redacted provider-call
  artifacts, and child-run approval records.
- Pending provider approvals pause the orchestration summary with
  `blocked_child_id` and child approval ids; downstream children are not
  materialized while a child is paused.
- Failed child runs stop downstream scheduling, mark the blocked child, and
  preserve the child run's normal failure evidence.
- `agent-harness orchestration resume <id>` refreshes existing child run
  summaries, refuses to continue while the blocked child is still paused or
  failed, and skips already-started children after their approvals complete.
- Generated handoffs remain deterministic safe metadata; raw provider payloads
  stay in child run provider artifacts and are not copied into aggregate
  handoffs.

### Out of scope

- Live-provider orchestration demos as required release gates.
- Provider-generated handoff summaries.
- Retrying failed children with modified specs.

---

## Phase 6: Orchestration Evidence Is Exported And Exposed Through Read-Only MCP

**User stories covered**

- Story 3: reviewers can audit aggregate evidence.
- Story 12: security reviewers can verify safe resource exposure.
- Story 14: MCP clients can read orchestration evidence without tools.

**Observable behaviors**

- `agent-harness orchestration export <id>` writes stable JSON export evidence.
- `agent-harness mcp resources list --json` includes orchestration resources
  when orchestration artifacts exist.
- MCP reads return safe envelopes for orchestration summary, manifest, events,
  children, and handoffs.
- MCP access logs remain metadata-only.
- Unsafe orchestration resource ids, traversal attempts, and mutation requests
  return denial envelopes.

**First RED test**

- An integration test creates a completed orchestration, lists MCP resources,
  reads `agent-harness://orchestrations/<id>/summary`, and asserts safe content,
  metadata-only access log entry, and no advertised MCP tools.

### What to build

Add orchestration JSON export and extend the existing MCP resource registry,
URI parser, safe envelopes, and access logging for read-only orchestration
artifacts.

### Acceptance criteria

- [x] Export references child artifacts without copying raw sensitive provider
      payloads.
- [x] MCP list/read covers orchestration collection and core artifacts.
- [x] MCP denial behavior covers unsafe ids and unsupported mutation shapes.
- [x] MCP access logs include request type, orchestration id when applicable,
      profile, result, redaction status, and denial reason.
- [x] MCP still advertises no tools.

### Phase 6 implementation notes

- Added `agent-harness orchestration export <id>` for stable
  `orchestration_export.v1` JSON evidence under `.agent-harness/exports/`.
- Exports include aggregate summary, manifest, events, approvals, handoffs,
  artifact index, and child artifact references; they do not copy raw child
  provider payload artifacts.
- Extended MCP resources with the orchestration collection plus summary,
  manifest, events, children, and handoffs.
- MCP orchestration reads return normal resource envelopes with safe relative
  source artifacts, metadata-only access logs, and `orchestration_id` when
  applicable.
- Unsafe orchestration ids and mutation-shaped resource names such as `run`,
  `approve`, and `resume` return denial envelopes. MCP still advertises no
  tools and does not execute orchestration operations.

### Out of scope

- MCP orchestration run, approve, resume, or provider execution.
- Operator API and static UI changes.

---

## Phase 7: Golden Path And Release Readiness Prove V11

**User stories covered**

- Story 15: release maintainer has deterministic acceptance evidence.
- Story 16: public docs match implemented behavior.
- Story 17: maintainers can extend the boundary without dead architecture.

**Observable behaviors**

- `examples/orchestration_workflow/` demonstrates a deterministic local
  planner/implementer/reviewer/tester dry-run over a small Python fixture.
- Release readiness requires orchestration demo evidence, policy gates,
  artifact checks, inspect/export evidence, MCP resource reads, MCP access-log
  evidence, docs check, and changelog entry.
- README, roadmap, architecture, security, MCP boundary, and release-readiness
  docs describe implemented V11 behavior and keep deferred multi-agent features
  in roadmap/future scope.

**First RED test**

- A release-readiness integration test runs the V11 orchestration smoke path in
  a temporary workspace and expects required orchestration gates to be present
  and passing in the readiness report.

### What to build

Add the V11 example, expected outputs where useful, release-readiness evidence
collectors, docs updates, changelog entry, and docs-check claim guards for the
new implemented scope and deferred future scope.

### Acceptance criteria

- [x] The V11 example runs from a clean checkout without external services.
- [x] Release readiness reports required orchestration gates.
- [x] Docs claim local sequential policy-mediated orchestration only.
- [x] Docs explicitly defer parallel execution, nested orchestration, hosted
      APIs, MCP tools/execution, operator UI support, and enterprise governance.
- [x] Full required local checks pass for release acceptance.

### Phase 7 implementation notes

- Added `examples/orchestration_workflow/` as the deterministic V11 golden path
  with local config, explicit orchestration policy, a Python fixture, and a
  planner -> implementer -> reviewer -> tester dry-run spec.
- Extended `release_readiness.v1` with V11 orchestration gates for demo
  presence, policy/role authority, aggregate and child artifacts, generated
  handoffs, inspect/export evidence, read-only MCP orchestration reads, and
  metadata-only MCP access logs.
- Updated public docs and release metadata for `v1.7.0`. Operator UI support
  and enterprise governance remain future-only. V11 does not support hosted
  APIs. Parallel multi-agent orchestration remains future-only. Nested
  orchestration remains future-only. MCP execution for multi-agent
  orchestration remains future-only.

### Out of scope

- External package publishing.
- External provider smoke tests as required gates.
- Hosted or enterprise deployment evidence.

## Cross-Phase Invariants

- Existing single-agent `agent-harness run` behavior remains compatible.
- Existing `policy.v2` files without `orchestration` remain valid for
  single-agent runs and deny orchestration by default.
- No child run bypasses `HarnessRuntime`, `PolicyEngine`, provider gates, tool
  execution policy, redaction, or approval binding checks.
- Supervisor approval never implies child mutation approval.
- Child authority can only narrow, never widen, selected policy authority.
- Generated handoffs are deterministic, redacted, policy-mediated, and
  dependency-scoped.
- Raw provider prompts, raw provider responses, secrets, credentials, private
  environment values, and denied context text never enter handoffs, exports, or
  MCP resources.
- All orchestration behavior is inspectable through public CLI artifacts before
  it is considered complete.
- MCP remains read-only and advertises no tools.
- Tests verify public behavior through CLI, artifacts, MCP resources, and
  release readiness rather than private helper shape.
- Documentation must not claim parallel, nested, hosted, MCP-execution,
  operator-UI, or enterprise multi-agent behavior until separate tested plans
  implement those capabilities.
