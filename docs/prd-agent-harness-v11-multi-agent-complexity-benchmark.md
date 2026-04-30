# PRD: Agent Harness V11 Multi-Agent Complexity Benchmark

This PRD amends the V11 policy-mediated orchestration track. The original
requirement was phrased as a V10 requirement, but this repository already uses
V10 for the schema-boundary refactor. The benchmark belongs with V11 because it
measures whether V11 orchestration roles improve outcomes over a normal
single-agent run.

## Problem Statement

Agent Harness now has local sequential orchestration for planner, implementer,
reviewer, and tester child runs. That capability is intentionally constrained
by policy, approvals, generated handoffs, and auditable child evidence. Without
a comparative benchmark, however, orchestration can still become a source of
unmeasured complexity.

More child agents can add extra handoffs, tool calls, approvals, artifacts, and
runtime cost. Those costs may be justified when a role catches defects, improves
approval correctness, clarifies failure attribution, or produces more complete
evidence. They are not justified simply because the workflow has more roles.

Today benchmark sample packs prove that local cases can import into workspaces,
run through the native runtime, and export evidence-backed results. They do not
compare a single-agent baseline against orchestration variants, and they do not
answer whether planner, reviewer, or tester roles improved measurable control
or quality for a fixture.

The affected actors are:

- release maintainers who need evidence before promoting orchestration roles
- benchmark maintainers who need repeatable fixture comparisons
- policy reviewers who need proof that orchestration does not widen authority
- developers who need to know when a multi-agent mode is worth its overhead
- documentation reviewers who need public claims to match measured behavior

## Solution

Add a benchmark comparison workflow that runs every eligible orchestration
fixture against a single-agent baseline. The first public surface is
`agent-harness benchmark compare`, which produces a stable comparison artifact
that links to baseline run evidence, orchestration evidence, child run evidence,
handoffs, approvals, and exports.

The comparison workflow evaluates these modes:

1. single-agent baseline
2. planner -> implementer
3. planner -> implementer -> reviewer
4. planner -> implementer -> reviewer -> tester, only when executable tests
   exist for the case

The benchmark starts with bundled local samples. A later version may add an
explicit per-case allowlist for broader packs, but V11 comparison should not
run arbitrary external benchmarks by default.

The benchmark records metrics for task success, tests passed, policy
violations, approval correctness, child run count, tool call count, token and
runtime cost when available, handoff count, handoff size, coordination overhead
ratio, defects caught by reviewer or tester, failure attribution clarity, and
artifact completeness.

The comparison result should recommend role retention only when a role improves
measurable control or quality. Roles that add overhead without measurable
benefit are flagged as removal candidates. The benchmark reports this evidence;
it does not automatically change default orchestration roles.

The solution deliberately avoids parallel execution, nested orchestration,
shared raw memory between child runs, hosted benchmark execution, live provider
requirements, public benchmark comparability claims, or automatic role-default
changes.

## User Stories

1. As a release maintainer, I want every orchestration fixture compared against
   a single-agent baseline, so that multi-agent roles are accepted only when
   they improve measured outcomes.
2. As a benchmark maintainer, I want a public comparison command, so that local
   benchmark evidence can be reproduced from a clean checkout.
3. As a policy reviewer, I want comparison runs to preserve normal policy and
   approval gates, so that orchestration cannot bypass single-agent safety
   controls.
4. As a developer, I want to see tool call, child run, handoff, and overhead
   metrics per mode, so that added coordination cost is visible.
5. As a reviewer, I want generated handoffs evaluated for usefulness, so that
   downstream roles are not rewarded for receiving irrelevant summaries.
6. As a tester, I want tester mode to run only for cases with executable test
   commands, so that the benchmark does not fabricate test coverage.
7. As a release maintainer, I want reviewer and tester defect catches recorded,
   so that added roles are credited only for observable quality improvements.
8. As a maintainer, I want role recommendations to be evidence-only, so that
   defaults are not changed automatically by one benchmark result.
9. As a documentation reviewer, I want docs to avoid claiming that more agents
   are better by default, so that public capability claims stay honest.
10. As a security reviewer, I want downstream child runs to receive only
    policy-filtered generated handoffs, so that raw child memory never becomes
    shared state.

## Behavioral Requirements

1. `agent-harness benchmark compare <pack_id> <case_id>` runs a single bundled
   case through the single-agent baseline and all eligible orchestration modes.
2. `agent-harness benchmark compare <pack_id>` runs every bundled case in the
   pack through the same comparison workflow.
3. A comparison result is invalid if the single-agent baseline did not run or
   cannot be inspected.
4. The command writes `benchmark_comparison_result.v1` for a single case and
   `benchmark_comparison_suite.v1` for pack-level comparison.
5. Comparison artifacts link to baseline run artifacts, orchestration summary,
   orchestration export, child run summaries, handoff artifacts, approval
   records, and benchmark result artifacts where applicable.
6. The benchmark records task success for every mode using existing run and
   orchestration status evidence.
7. The benchmark records tests passed only from real `run_tests` observations
   or explicit absence of executable tests; dry-run test skips do not count as
   passed tests.
8. The tester mode is generated only when the benchmark case includes executable
   `test_commands`.
9. The benchmark records policy violations from denied policy decisions,
   denied tool observations, or failed orchestration authority checks.
10. The benchmark records approval correctness from supervisor approval records
    and child-run approval records, including pending, approved, denied, and
    binding-drift outcomes.
11. The benchmark records child run count from orchestration summary children
    and uses one as the single-agent baseline count.
12. The benchmark records tool call count from `model_action` events and tool
    observations in run exports.
13. The benchmark records token, runtime, and cost metrics when run or provider
    evidence exposes them; otherwise those fields are explicit `unavailable`
    values, not inferred estimates.
14. The benchmark records handoff count and handoff size from orchestration
    handoff records.
15. The benchmark records a coordination overhead ratio that compares
    supervisor events, extra child runs, supervisor approvals, and handoffs
    against child tool activity.
16. The benchmark evaluates each generated handoff as included, policy-denied,
    budget-excluded, included-but-unused, or used-by-downstream.
17. The benchmark records defects caught by reviewer or tester only when a
    downstream reviewer/tester mode observes a failure, denial, approval issue,
    failed test, or artifact gap not already surfaced by an upstream mode.
18. The benchmark records failure attribution clarity based on whether the
    result identifies the failing child or baseline run, failed tool or test,
    relevant policy decision, and linked artifact.
19. The benchmark records artifact completeness for required baseline,
    orchestration, child, handoff, approval, export, and comparison artifacts.
20. Role recommendations never mark a role as default unless it improves
    measurable control or quality without worsening policy violations.
21. Roles that add overhead without measurable improvement are flagged as
    `remove_candidate`.
22. Downstream child runs receive only generated, policy-filtered handoffs;
    raw child prompts, raw provider responses, raw run memory, and denied
    context text are never shared.
23. Comparison orchestration remains sequential. The benchmark does not create
    parallel or nested orchestration specs.
24. Existing `agent-harness benchmark run` behavior and `benchmark_result.v1`
    artifacts remain compatible.
25. Existing `agent-harness orchestration run` CLI behavior remains compatible
    unless a later implementation plan explicitly expands it with tests.

## Implementation Decisions

- Add the comparison workflow under the `agent_harness.benchmarks` boundary
  because benchmark comparison owns fixture staging, result aggregation, and
  evidence-backed benchmark artifacts.
- Use `agent_harness.orchestration` as the execution backend for orchestrated
  modes. Do not make benchmarks a second orchestration implementation.
- Introduce `agent-harness benchmark compare` as the first public interface for
  comparison evidence. Keep `benchmark run` focused on one single-agent case.
- Add boundary-owned comparison schemas in `agent_harness.benchmarks.schema`.
  Preserve existing `benchmark_result.v1`.
- Generate comparison mode specs from benchmark cases. Do not require benchmark
  pack authors to hand-write orchestration specs for the first bundled path.
- Extend orchestration child declarations only as needed to carry normal
  `task.v2` fields required for comparable child execution, such as
  `context_queries` and `test_commands`.
- The benchmark may use a benchmark-owned execution path that allows real
  `run_tests` for tester mode while preserving existing policy, path,
  provider, and approval gates.
- Store comparison artifacts under `.agent-harness/benchmarks/comparisons/`.
- Keep baseline and each orchestration mode in isolated workspaces so generated
  files, approvals, and artifacts cannot contaminate other modes.
- Use existing run exports and orchestration exports as measurement inputs
  instead of reading private runtime objects.
- Add roadmap documentation for explicit benchmark allowlists, but keep V11
  initial scope to bundled local samples.

## Testing Decisions

- Test comparison behavior through public CLI commands, persisted artifacts,
  run exports, orchestration exports, and benchmark comparison results.
- Unit tests should cover mode eligibility, comparison schema validation,
  metric aggregation, handoff usefulness classification, overhead ratio
  calculation, and role recommendation rules.
- Integration tests should cover single-case comparison, pack-level comparison,
  skipped tester mode without executable tests, included tester mode with a
  deterministic test fixture, approval correctness, and artifact completeness.
- Adversarial tests should cover policy denial, role escalation attempts,
  handoff leakage attempts, missing baseline evidence, tampered comparison
  links, and unavailable cost metrics.
- Eval coverage should fail when an orchestration fixture lacks a single-agent
  baseline or when comparison evidence is missing required links.
- Documentation checks should prevent current docs from claiming that more
  agents improve outcomes by default.
- Tests should not assert private helper names or private file layout beyond
  public artifact contracts.

## Out of Scope

- Implementing the benchmark in this planning branch.
- Replacing the existing V10 schema-boundary PRD or plan.
- Parallel orchestration.
- Nested orchestration.
- Hosted benchmark execution or remote agent workers.
- Live provider calls as required benchmark evidence.
- Public SWE-bench or Terminal-Bench comparability claims.
- Automatic role default changes based on benchmark output.
- Automatic deletion of roles from orchestration policy.
- Operator UI support for benchmark comparison.
- MCP execution or benchmark comparison through MCP tools.
- External benchmark pack allowlists in the first implementation.

## Further Notes

The core tradeoff is measurement before expansion. A planner, reviewer, or
tester role should earn its place by improving an observable outcome or control
surface. If it only increases handoff volume, child runs, tool calls, or runtime
without improving quality or governance, the benchmark should make that visible.

The highest implementation risks are accidental authority widening during
generated orchestration specs, treating dry-run test skips as real test passes,
shared state leakage between child runs, and vague failure attribution. The plan
should therefore start with a small comparison artifact that proves the baseline
requirement before adding richer metric interpretation.
