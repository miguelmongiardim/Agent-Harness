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

- [ ] `docs/prd-agent-harness-v11.md` exists and follows the PRD template.
- [ ] `plans/agent-harness-v11.md` exists and uses vertical tracer-bullet
      phases.
- [ ] Docs checks fail on unsupported multi-agent capability claims.
- [ ] README and roadmap do not describe V11 orchestration as implemented until
      code and release evidence exist.
- [ ] No runtime, policy, storage, MCP, or CLI implementation is added in this
      phase beyond documentation guards.

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

- [ ] The CLI command group exists with `run` help text.
- [ ] Minimal `orchestration.v1` validation errors are actionable.
- [ ] Missing `policy.v2.orchestration` denies orchestration.
- [ ] Denial does not launch `HarnessRuntime`.
- [ ] Existing `agent-harness run` behavior is unchanged.

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

- [ ] One planner child completes through `HarnessRuntime` in dry-run mode.
- [ ] Child run artifacts are normal run artifacts under `.agent-harness/runs/`.
- [ ] Aggregate orchestration artifacts live under `.agent-harness/orchestrations/`.
- [ ] Inspect output references child artifacts without copying raw run content.
- [ ] No provider, write, handoff, approval, MCP, or release behavior is needed
      for this phase.

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

- [ ] Dependency cycles are rejected with clear validation errors.
- [ ] Children run in dependency order.
- [ ] Handoffs are written under the orchestration artifact directory.
- [ ] Downstream child context includes direct dependency handoffs only.
- [ ] Handoffs exclude raw provider prompts, raw provider responses, secrets,
      credentials, and denied context text.

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

- [ ] Role ceilings are enforced for all four V11 roles.
- [ ] Effective authority records are inspectable in orchestration evidence.
- [ ] Risky plans pause before any child starts.
- [ ] Approved risky plans resume only when bindings still match.
- [ ] Child patch approvals remain separate child-run approvals.
- [ ] Multiple write-capable children may appear only under sequential execution;
      no more than one writer is active at a time.

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

- [ ] Provider default inheritance attempts are denied or ignored safely.
- [ ] Explicit provider child runs use existing provider gates and artifacts.
- [ ] Child pause stops the supervisor and marks the blocked child.
- [ ] Child failure stops downstream scheduling.
- [ ] Resume does not rerun completed children.
- [ ] Handoffs and aggregate exports never include raw provider payloads.

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

- [ ] Export references child artifacts without copying raw sensitive provider
      payloads.
- [ ] MCP list/read covers orchestration collection and core artifacts.
- [ ] MCP denial behavior covers unsafe ids and unsupported mutation shapes.
- [ ] MCP access logs include request type, orchestration id when applicable,
      profile, result, redaction status, and denial reason.
- [ ] MCP still advertises no tools.

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

- [ ] The V11 example runs from a clean checkout without external services.
- [ ] Release readiness reports required orchestration gates.
- [ ] Docs claim local sequential policy-mediated orchestration only.
- [ ] Docs explicitly defer parallel execution, nested orchestration, hosted
      APIs, MCP tools/execution, operator UI support, and enterprise governance.
- [ ] Full required local checks pass for release acceptance.

### Out of scope

- Publishing or tagging `v1.7.0`.
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
