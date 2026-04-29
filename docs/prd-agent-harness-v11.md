# PRD: Agent Harness V11 Policy-Mediated Multi-Agent Orchestration

V11 targets `v1.7.0` after the V10 schema-boundary refactor. It introduces a
local, policy-mediated supervisor for coordinating multiple child task runs
without turning Agent Harness into a hosted platform, an MCP execution surface,
or an in-process multi-agent graph runtime.

## Problem Statement

Agent Harness can run one policy-mediated task at a time and records strong
local evidence for context, tools, approvals, provider calls, skills, templates,
evals, exports, and MCP resource reads. Complex software work often needs more
than one role: planning, implementation, review, and test validation. Today a
user must run those roles manually as separate tasks, copy or summarize results
by hand, and reconstruct the relationship between runs from chat history or
local notes.

That manual workflow creates three problems.

First, handoffs are not first-class evidence. A reviewer cannot inspect exactly
which output from an earlier run was given to a later run, whether it was
redacted, or which policy decision allowed it into context.

Second, authority is hard to reason about across roles. A planner, reviewer,
and tester should not inherit the same mutation authority as an implementer, and
no child run should be able to widen the policy profile, tool set, provider use,
or path authority selected for the orchestration.

Third, broad multi-agent behavior would be risky if added directly to MCP,
LangGraph, provider execution, or an unrestricted parallel scheduler. Agent
Harness needs a narrow local orchestration release that proves policy, approval,
audit, and release-readiness behavior before adding more execution models.

The affected actors are:

- developers who want repeatable multi-step agent workflows without losing audit
  evidence
- reviewers who need to inspect role decisions, child runs, generated handoffs,
  and approvals
- policy authors who need explicit limits for role authority and orchestration
  behavior
- security reviewers who need proof that orchestration cannot bypass redaction,
  provider-input gates, path policy, or approval bindings
- release maintainers who need deterministic local demo and readiness evidence

## Solution

V11 adds a local `agent_harness.orchestration` boundary that supervises child
runs through the existing native runtime. An orchestration is defined by an
`orchestration.v1` input file with inline child declarations. The supervisor
validates the spec, applies a single selected policy profile, materializes each
child declaration into a generated `task.v2` artifact, runs children in a
deterministic dependency order, records generated handoffs, and writes aggregate
orchestration evidence under `.agent-harness/orchestrations/<orchestration-id>/`.

The user-facing workflow is:

1. Add explicit orchestration rules to `policy.v2`.
2. Write an `orchestration.v1` spec with child agents such as planner,
   implementer, reviewer, and tester.
3. Run `agent-harness orchestration run <spec> --dry-run` to validate the
   policy, schedule child runs, and produce inspectable evidence.
4. Approve a risky orchestration plan when any child may write files or use a
   provider.
5. Resume the orchestration after approvals or after a paused child run is
   approved through the existing child-run approval command.
6. Inspect the aggregate orchestration, child run links, generated handoffs, and
   policy decisions through CLI or read-only MCP resources.
7. Verify the V11 golden path through release-readiness evidence.

The supervisor is not a new agent runtime. It delegates child task execution to
`HarnessRuntime`, preserving existing context assembly, tool mediation,
provider-use approval, provider-input approval, patch approval, git commit
approval, checkpoints, redaction, and run storage behavior. The supervisor owns
only orchestration-level validation, scheduling, authority narrowing, aggregate
evidence, generated handoff construction, and orchestration-plan approvals.

V11 deliberately avoids parallel execution, nested orchestration, MCP tools,
MCP run execution, operator UI changes, hosted APIs, remote agents, provider-
generated handoffs, cross-profile child policies, and organization-wide agent
governance.

## User Stories

1. As a developer, I want to define a local multi-agent workflow in one
   `orchestration.v1` file, so that planning, implementation, review, and test
   steps are reproducible.
2. As a developer, I want the supervisor to materialize child tasks into normal
   `task.v2` artifacts, so that each child remains inspectable through existing
   run evidence.
3. As a reviewer, I want an orchestration summary that links every child run,
   role, status, dependency, and handoff, so that I can audit the whole workflow
   without reconstructing it manually.
4. As a policy author, I want orchestration to require an explicit
   `policy.v2.orchestration` section, so that existing policies do not gain
   multi-agent behavior accidentally.
5. As a policy author, I want fixed role ceilings for planner, implementer,
   reviewer, and tester, so that child roles cannot expand authority beyond
   their purpose.
6. As a security reviewer, I want child authority to be the intersection of the
   selected policy, role ceiling, child declaration, task constraints, and path
   policy, so that no child can widen tool, path, or provider access.
7. As an approval reviewer, I want risky orchestration plans to pause before any
   child starts when a child may write files or use a provider, so that the
   whole plan is reviewed before risky execution begins.
8. As an approval reviewer, I want orchestration-plan approvals to bind to the
   exact child plan and selected policy, so that stale or tampered plans cannot
   resume.
9. As an implementer, I want write-capable children to use the existing patch
   and git approval paths, so that orchestration does not create a separate
   mutation bypass.
10. As a provider user, I want provider-backed children to require explicit
    child `provider_profile` declarations, so that providers are never inherited
    accidentally from project defaults.
11. As a downstream child agent, I want dependency handoffs to enter context as
    policy-mediated generated context, so that I receive relevant upstream
    results without direct access to raw child evidence.
12. As a security reviewer, I want generated handoffs and MCP resources to avoid
    raw provider prompts, raw provider responses, secrets, credentials, and
    machine-local paths, so that orchestration does not leak sensitive data.
13. As an operator, I want a paused or failed child to stop the orchestration and
    record the blocked child, so that recovery is deliberate and inspectable.
14. As an MCP client user, I want read-only MCP resources for orchestration
    evidence, so that standard review clients can inspect aggregate results
    without getting execution tools.
15. As a release maintainer, I want a deterministic local golden-path demo and
    release-readiness gates, so that V11 can be accepted from a clean checkout.
16. As a documentation reviewer, I want public docs to clearly separate V11
    local orchestration from future parallel, hosted, MCP-execution, nested, and
    enterprise multi-agent behavior.
17. As a maintainer, I want orchestration contracts to live in the
    boundary-owned schema layout established by V10, so that new public models
    do not recreate a root schema dumping ground.

## Behavioral Requirements

1. `agent-harness orchestration run <spec> --dry-run` rejects an
   `orchestration.v1` spec with clear validation errors when child ids,
   dependencies, roles, paths, tools, provider references, or schema versions
   are invalid.
2. An orchestration cannot run when the selected `policy.v2` profile lacks an
   explicit `orchestration` section.
3. A valid orchestration with explicit policy enablement creates an
   orchestration id and writes aggregate evidence under
   `.agent-harness/orchestrations/<orchestration-id>/`.
4. The supervisor materializes every child declaration into a generated
   `task.v2` artifact before launching the child run.
5. Child runs execute through the existing native runtime and produce normal run
   artifacts under `.agent-harness/runs/<run-id>/`.
6. The orchestration summary records schema version, orchestration id, source
   spec, selected policy profile, status, child statuses, child run ids,
   dependencies, approvals, handoff artifacts, started time, ended time, and
   artifact references.
7. The orchestration event log records validation, policy decisions, plan
   approval requests, child start/finish, handoff creation, pause, resume,
   failure, and completion events.
8. Supported child roles are exactly `planner`, `implementer`, `reviewer`, and
   `tester` in V11.
9. Default role ceilings are narrow: planner may read and search; implementer
   may read, search, and patch; reviewer may read, search, and inspect git
   status; tester may read, search, and run allowed tests.
10. Effective child tools are the intersection of policy allowed tools, role
    ceilings, child-declared tools, and task constraints.
11. A child cannot write outside policy write roots, cannot read denied paths,
    and cannot use tools excluded by either policy or role ceiling.
12. V11 scheduling is deterministic and sequential. Independent children may
    be ordered deterministically, but no OS-level parallel child execution is
    part of this release.
13. Multiple write-capable children may exist in a single orchestration only
    because execution is sequential. The supervisor must never have more than
    one active writer child.
14. Nested orchestration is rejected. Children are materialized only as `task.v2`
    runs, not as child orchestration specs.
15. A risky orchestration plan pauses for `orchestration_plan` approval before
    any child starts when any child can write files or declares provider use.
16. An approved orchestration plan resumes only if the selected policy, child
    plan, child authority summary, dependency graph, and proposed risk summary
    still match the approval binding.
17. Child patch, template, provider, provider-input, and git approvals continue
    to use existing child-run approval records and exact-effect checks.
18. A child uses a provider only when that child declaration explicitly names a
    configured provider profile. Project default providers are not inherited by
    orchestration children.
19. Provider-backed child runs still evaluate provider trust-zone policy,
    provider-input policy, redaction, recorded fixture behavior, and live smoke
    opt-in exactly as normal runs do.
20. After a child completes, the supervisor produces a deterministic generated
    handoff summary from safe child evidence, not from a provider call.
21. A child receives generated handoffs only from its direct `depends_on`
    children.
22. Generated handoffs enter downstream child context as generated,
    policy-mediated context with provenance back to the orchestration id,
    upstream child id, upstream run id, and policy decision id.
23. Handoffs never include raw provider requests, raw provider responses,
    secrets, credentials, private environment values, or denied context text.
24. If any child pauses or fails, the supervisor stops scheduling new children,
    records the blocked child, and marks the orchestration paused or failed.
25. `agent-harness orchestration resume <orchestration-id>` continues only after
    required orchestration-plan approvals or child-run approvals are complete
    and bindings still match.
26. `agent-harness orchestration inspect <orchestration-id>` returns the
    aggregate summary, events, child run links, approval records, handoff
    metadata, and artifact index without executing children.
27. `agent-harness orchestration export <orchestration-id>` writes a stable JSON
    export that references child run artifacts without copying raw sensitive
    provider payloads.
28. Read-only MCP resources expose orchestration collection, summary, manifest,
    events, children, and handoffs through safe envelopes and append metadata-
    only MCP access logs.
29. MCP does not expose orchestration tools, approval mutation, run execution,
    provider execution, patch application, or resume operations in V11.
30. Release readiness reports V11 orchestration demo, policy, artifact,
    inspection, MCP resource, access-log, and documentation-gate evidence.

## Implementation Decisions

- Add `agent_harness.orchestration` as the core V11 boundary. It owns
  orchestration spec loading, DAG validation, role authority narrowing,
  scheduling, orchestration-plan approvals, aggregate storage, handoff
  construction, and inspection/export helpers.
- Implement V11 as a supervisor over `HarnessRuntime`, not as a replacement
  runtime and not as an in-process graph executor.
- Assume the V10 schema-boundary refactor has landed before V11 implementation.
  New models should live in boundary-owned modules such as
  `agent_harness.orchestration.schema` and should not reintroduce a root schema
  module.
- Add `orchestration.v1` as a new public input schema. It uses inline child
  declarations and materializes generated `task.v2` files into orchestration
  artifacts.
- Keep `task.v2` focused on one child task. Do not introduce a new task schema
  version for V11.
- Extend `policy.v2` with an explicit `orchestration` contract. Missing
  orchestration policy denies orchestration while preserving existing single-
  agent run compatibility.
- The default v1.7 policy emitted by `agent-harness init` should include a safe
  orchestration section with local sequential orchestration enabled, narrow role
  ceilings, no nested orchestration, deterministic handoffs, and risky-plan
  approval enabled.
- Store orchestration evidence under
  `.agent-harness/orchestrations/<orchestration-id>/`, separate from normal run
  directories.
- Use append-only orchestration events modeled after run events, but keep them
  distinct from child run events.
- Add an `orchestration_plan` approval subject for supervisor-level plan
  approval. It binds the selected policy, child authority summary, dependency
  graph, materialized child task hashes, risk summary, and checkpoint-equivalent
  orchestration state hash.
- Preserve existing child-run approval boundaries. A supervisor approval never
  implies approval for a child patch, template apply, provider input, provider
  use, or git commit.
- Extend context assembly to accept generated orchestration handoff inputs as a
  policy-mediated generated context source. The implementation may introduce a
  new context schema version if needed, but it must preserve existing readers
  for current run artifacts.
- Extend MCP resource registries for read-only orchestration evidence. Keep MCP
  tools, write-capable MCP, approval mutation, provider execution, and run
  creation outside V11.
- Extend release readiness with required orchestration gates and a deterministic
  `examples/orchestration_workflow/` golden path.
- Documentation must update roadmap and capability boundaries only when the
  implementation is complete. Planning docs may describe intended V11 behavior
  as future work.

## Testing Decisions

- Test orchestration primarily through public CLI commands, persisted artifacts,
  child run artifacts, MCP resource reads, and release-readiness reports.
- Unit tests should cover schema validation, DAG validation, role ceilings,
  authority intersection, policy-section denial, plan approval binding hashes,
  deterministic scheduling, and handoff redaction rules.
- Integration tests should cover a minimal read-only orchestration, a sequential
  planner/implementer/reviewer/tester dry-run, handoff propagation into child
  context, risky-plan approval and resume, child pause propagation, child
  failure propagation, explicit provider child use, and CLI inspect/export.
- Adversarial tests should cover missing orchestration policy, role escalation,
  tool escalation, write path escape, nested orchestration, dependency cycles,
  stale plan approvals, tampered child task artifacts, provider default
  inheritance attempts, raw provider payload leakage, denied handoff content,
  and unsafe MCP resource identifiers.
- MCP tests should verify list/read behavior for orchestration resources,
  denial envelopes, metadata-only access logs, and absence of tools or mutation
  behavior.
- Release tests should verify `examples/orchestration_workflow/`, required
  release-readiness gates, docs checks, and no public claims for parallel,
  hosted, nested, MCP-execution, or enterprise multi-agent support.
- Do not test private scheduler helper names or storage implementation details
  when public artifact and CLI behavior can prove the same requirement.

## Out of Scope

- In-process multi-agent graph execution.
- Parallel child execution.
- Nested orchestration.
- MCP tools, MCP approval mutation, MCP run execution, and MCP provider
  execution.
- Operator API or static UI support for orchestration.
- Hosted orchestration APIs or remote agent workers.
- Multi-user identity, enterprise policy governance, centralized control plane,
  attestation, or compliance readiness.
- Provider-generated handoff summaries.
- Automatic child policy-profile switching or per-child looser policy profiles.
- Remote template catalogs, remote skill catalogs, and network skill
  installation.
- Automatic git commits for orchestration output.
- Replacing `HarnessRuntime` or making LangGraph the primary orchestration
  runtime.

## Further Notes

The central tradeoff is to make orchestration explicit and inspectable before
making it powerful. Sequential local supervision gives users a real multi-step
workflow while preserving the policy, approval, storage, and release-readiness
architecture already proven by earlier releases.

The largest risks are accidental authority widening, treating generated
handoffs as trusted raw evidence, leaking provider payloads through aggregate
artifacts, and creating a second mutation path outside child-run approvals. V11
should keep those risks visible through policy-denial defaults, exact approval
bindings, role ceilings, redacted generated context, read-only MCP resources,
and required release gates.

V11 planning assumes V10 schema ownership lands first. If V11 is implemented
before V10 is complete, the first implementation slice should either rebase onto
V10 or keep orchestration models isolated enough that they can be moved cleanly
into boundary-owned schema modules after the V10 refactor.
