# Plan: Agent Harness V11 Multi-Agent Complexity Benchmark

> Source PRD:
> [docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md](../docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md)

This plan follows the PRD -> Plan -> TDD workflow. It is intentionally limited
to planning; do not implement these phases until a separate implementation
request starts TDD execution.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness benchmark compare <pack_id>
  [case_id]`. Existing `benchmark run` behavior remains unchanged.
- **Key models**: add comparison result, comparison suite, mode result,
  metric, handoff usefulness, and role recommendation records under the
  benchmark schema boundary.
- **Schema**: use `benchmark_comparison_result.v1` and
  `benchmark_comparison_suite.v1`; preserve `benchmark_result.v1`.
- **Storage**: write comparison artifacts under
  `.agent-harness/benchmarks/comparisons/`, with links to run, orchestration,
  child, handoff, approval, and export artifacts.
- **Runtime boundary**: benchmark comparison stages fixtures and delegates
  single-agent execution to the native runtime and orchestrated execution to
  the orchestration boundary.
- **Policy boundary**: comparison runs use normal policy, path, provider,
  approval, and role-ceiling checks. Benchmark generation cannot widen
  authority.
- **Approval model**: supervisor approvals and child-run approvals remain
  distinct. Comparison evidence records their correctness without creating a
  new approval mechanism.
- **Audit model**: metrics are derived from public run exports, orchestration
  exports, events, summaries, and handoff records.
- **External service boundary**: bundled local samples are the initial scope.
  No network, live provider, hosted benchmark, parallel orchestration, or
  external benchmark comparability claim is required.

---

## Phase 0: Comparison Scope Is Documented And Guarded

**User stories covered**

- Story 1: release maintainer requires a baseline for every orchestration
  fixture.
- Story 8: role recommendations are evidence-only.
- Story 9: docs avoid presenting role-count expansion as an improvement without
  comparison evidence.

**Observable behaviors**

- The PRD and plan exist as durable planning artifacts.
- Public docs can reference the benchmark as planned work without claiming it
  is implemented.
- Docs checks can reject unsupported claims that extra agents improve outcomes
  by default.

**First RED test**

- Add a docs-check test that fails when current capability docs present
  expanded multi-agent role chains as preferred without comparison evidence or
  imply evidence-backed default role selection before comparison evidence
  exists.

### What to build

Add only documentation guard behavior and planning references needed to keep
public claims honest. Do not add the comparison command or schemas in this
phase unless a docs-check behavior needs a constant or test fixture.

### Acceptance criteria

- [x] The PRD exists and follows the repo PRD template.
- [x] The plan exists and uses vertical tracer-bullet phases.
- [x] Docs checks reject unsupported role-count improvement claims.
- [x] README and roadmap mention comparison only as planned or future behavior.
- [x] No benchmark comparison runtime or CLI behavior is implemented.

### Out of scope

- Comparison schemas.
- `benchmark compare`.
- Metric aggregation.
- Orchestration spec generation.

### Implementation notes

- Added `unsupported_benchmark_comparison_claim` docs-check coverage for
  current-capability claims that expanded role chains are preferred without
  comparison evidence or that default role selection is evidence-backed before
  comparison evidence exists.
- README and roadmap now link the benchmark PRD and plan as planned/future work
  and explicitly keep `agent-harness benchmark compare`, comparison schemas,
  metric aggregation, handoff usefulness scoring, role recommendations, and
  default-role promotion out of current behavior.
- No benchmark comparison runtime, CLI, schema, metric, or orchestration spec
  generation behavior was added.

---

## Phase 1: One Case Produces A Baseline-First Comparison Artifact

**User stories covered**

- Story 1: every orchestration fixture is benchmarked against a baseline.
- Story 2: benchmark maintainer can reproduce comparison through CLI.
- Story 4: visible child/tool/handoff overhead begins with concrete evidence.

**Observable behaviors**

- `agent-harness benchmark compare local-samples terminal-readonly-inspect`
  runs the single-agent baseline first.
- The command writes one `benchmark_comparison_result.v1` artifact.
- The result is invalid if the baseline run is missing, failed to export, or
  cannot be inspected.
- The first orchestration mode compared is planner -> implementer.

**First RED test**

- An integration test runs the compare command for
  `terminal-readonly-inspect`, reads the comparison artifact, and asserts a
  baseline mode plus a planner-implementer mode with linked run and
  orchestration evidence.

### What to build

Create the minimal comparison command for one bundled case. Stage isolated
baseline and orchestration workspaces, run the baseline through the existing
benchmark path, generate a planner -> implementer orchestration spec, export
both evidence sets, and write the comparison artifact with basic success,
child-run count, tool-call count, handoff count, and artifact completeness.

### Acceptance criteria

- [x] The CLI prints the comparison artifact path or JSON result consistently
      with existing benchmark commands.
- [x] Baseline evidence is produced before orchestrated mode evidence.
- [x] The comparison result links to the baseline run export.
- [x] The comparison result links to the orchestration export and child run
      summaries.
- [x] No raw child memory or provider payload is copied into comparison
      artifacts.

### Out of scope

- Reviewer and tester modes.
- Pack-level comparison.
- Role recommendations.
- Runtime/cost metrics beyond explicit unavailable fields.

### Implementation notes

- Added `agent-harness benchmark compare <pack_id> <case_id>` for the first
  bundled case path, with Phase 1 coverage for
  `local-samples terminal-readonly-inspect`.
- The comparison runner stages separate baseline and planner -> implementer
  workspaces, runs the baseline through the existing benchmark path first,
  then runs a generated sequential orchestration dry run through the existing
  orchestration boundary.
- Added `benchmark_comparison_result.v1` and
  `benchmark_comparison_mode_result.v1` records under the benchmark schema
  boundary. The artifact links to the baseline run export, the orchestration
  export, and child run summaries using project-relative paths.
- The Phase 1 mode evidence records basic pass/status, child run count, tool
  observation count, handoff count, and artifact completeness without copying
  raw child memory or provider payloads.
- Pack-level comparison, reviewer/tester modes, role recommendations, and
  richer metric interpretation remain later phases.

---

## Phase 2: All Required Orchestration Modes Are Generated Sequentially

**User stories covered**

- Story 1: every orchestration fixture has all required comparable modes.
- Story 6: tester mode appears only when executable tests exist.
- Story 10: downstream children receive policy-filtered handoffs only.

**Observable behaviors**

- Planner -> implementer and planner -> implementer -> reviewer modes run for
  eligible bundled cases.
- Planner -> implementer -> reviewer -> tester mode runs only when the case
  declares executable `test_commands`.
- Generated orchestration specs remain sequential and non-nested.
- Downstream children receive only dependency-scoped generated handoffs.

**First RED test**

- An integration test compares a no-test bundled case and asserts tester mode
  is marked ineligible with a clear reason, then compares a test-enabled
  fixture and asserts tester mode is present.

### What to build

Extend mode generation to produce all required role chains. Carry normal task
fields needed by child runs, including context queries and test commands.
Preserve role ceilings and policy-filtered generated handoffs through the
existing orchestration boundary.

### Acceptance criteria

- [x] Required modes are generated deterministically.
- [x] Tester mode is skipped unless executable tests exist.
- [x] Generated children use role-appropriate allowed tools.
- [x] No child receives handoffs outside its direct dependencies.
- [x] Comparison evidence records mode eligibility and skip reasons.

### Out of scope

- Parallel scheduling.
- Explicit user-authored orchestration specs for benchmark cases.
- External benchmark pack allowlists.

### Implementation notes

- Extended `benchmark compare <pack_id> <case_id>` to emit baseline,
  planner -> implementer, planner -> implementer -> reviewer, and
  planner -> implementer -> reviewer -> tester mode records in deterministic
  order.
- Tester mode records `eligible=false`, `status=skipped`, and a clear skip
  reason unless the benchmark task declares executable `test_commands` and
  allows `run_tests`.
- Added the bundled `terminal-test-runner` fixture to prove tester-mode
  generation without pack-level comparison.
- Generated orchestration children carry role-appropriate tools, context
  queries, and tester `test_commands` into materialized child `task.v2`
  artifacts while preserving existing role ceilings and policy-filtered
  direct-dependency handoffs.
- Pack-level comparison, metric interpretation, handoff usefulness scoring,
  and recommendations remain later phases.

---

## Phase 3: Metrics Prove Control, Cost, And Artifact Completeness

**User stories covered**

- Story 3: policy and approval gates remain visible.
- Story 4: coordination cost is measurable.
- Story 7: reviewer/tester defect catches are recorded.

**Observable behaviors**

- Every mode records task success, tests passed, policy violations, approval
  correctness, child run count, tool call count, handoff count, handoff size,
  coordination overhead ratio, failure attribution clarity, and artifact
  completeness.
- Token/runtime/cost metrics are recorded when available and explicitly marked
  unavailable otherwise.
- Reviewer/tester defect catches are recorded only from downstream observable
  evidence.

**First RED test**

- A unit or integration test loads a comparison result from known fixture
  evidence and asserts all required metric names exist with deterministic
  values or explicit unavailable status.

### What to build

Build metric extraction from run exports, orchestration exports, event logs,
handoff records, approvals, and artifact indexes. Keep metric derivation in the
benchmark boundary and avoid private runtime state.

### Acceptance criteria

- [x] Required metrics are present for every executed mode.
- [x] Dry-run test skips do not count as passed tests.
- [x] Policy violations are derived from policy decisions and denied tool
      observations.
- [x] Approval correctness distinguishes pending, approved, denied, and
      binding-drift cases.
- [x] Artifact completeness reports missing links with artifact names.

### Out of scope

- Estimated token or cost values when no evidence exists.
- Model-quality scoring beyond observed benchmark outcomes.
- Automatic release gating.

### Implementation notes

- Added `benchmark_comparison_metric.v1` records to each executed comparison
  mode. Required Phase 3 metric names are emitted for baseline and generated
  orchestration modes.
- Metrics are derived from linked run exports, child event logs, orchestration
  exports, handoff records, approval records/events, and artifact-completeness
  maps inside the benchmark boundary.
- `tests_passed` requires successful `run_tests` observations for declared
  `test_commands`; absent or dry-run-only test evidence is not counted as
  passed.
- Policy-violation metrics count denied policy decisions, denied tool
  observations, and orchestration authority failures when present.
- Approval metrics report pending, approved, denied, and binding-drift counts;
  the SWE-style fixture proves approved baseline patch evidence.
- Token, runtime, and cost metrics are explicitly marked unavailable when the
  linked evidence does not expose those values.
- Defect-catch metrics are present as deterministic zero counts until Phase 4
  interpretation adds handoff usefulness and role recommendation logic.

---

## Phase 4: Handoff Usefulness And Role Recommendations Are Evidence-Based

**User stories covered**

- Story 5: handoffs are evaluated for usefulness.
- Story 8: role recommendations are evidence-only.
- Story 9: no role becomes default without measured improvement.

**Observable behaviors**

- Each generated handoff is classified as included, policy-denied,
  budget-excluded, included-but-unused, or used-by-downstream.
- Role recommendations identify retained roles, neutral roles, and
  `remove_candidate` roles.
- A role is never recommended as default unless it improves measurable control
  or quality without worsening policy violations.

**First RED test**

- A unit test feeds synthetic mode metrics into the recommendation engine and
  asserts that a role adding overhead with no quality/control gain is marked
  `remove_candidate`, while a role that catches a defect is retained.

### What to build

Add comparison interpretation over existing metrics. Use conservative,
transparent recommendation rules and include enough explanation for a reviewer
to audit why a role was retained or flagged.

### Acceptance criteria

- [x] Handoff usefulness appears in comparison artifacts.
- [x] Role recommendations include reason codes and supporting metric names.
- [x] No recommendation mutates policy defaults or orchestration role lists.
- [x] Recommendation rules are deterministic and covered by behavior tests.

### Out of scope

- Automatic role removal.
- Automatic default-role promotion.
- Machine-learned scoring or provider-generated recommendations.

### Implementation notes

- Added `benchmark_comparison_handoff_usefulness.v1` records to generated
  orchestration modes. Classifications are derived from downstream
  `context_manifest.v2` evidence and distinguish used, policy-denied,
  budget-excluded, attached-but-unused, and recorded-only handoffs.
- Added `benchmark_comparison_role_recommendation.v1` records to comparison
  results. Recommendation rules compare eligible sequential modes, use reason
  codes plus supporting metric names, retain roles only for measurable quality
  or control gains, and flag policy regressions or overhead without gain as
  `remove_candidate`.
- Planner and implementer are neutral when only the combined planner ->
  implementer mode is available because the benchmark cannot isolate either
  role's individual contribution from that single mode.
- Recommendations are evidence records only; they do not mutate policy
  defaults, generated orchestration specs, or role lists.

---

## Phase 5: Pack-Level Comparison And Eval Evidence

**User stories covered**

- Story 2: benchmark maintainer can reproduce pack-level evidence.
- Story 8: role decisions remain evidence-only across cases.
- Story 9: docs and evals keep public claims honest.

**Observable behaviors**

- `agent-harness benchmark compare local-samples` runs every bundled case in
  the pack and writes `benchmark_comparison_suite.v1`.
- The suite result aggregates per-case comparison artifacts without hiding
  individual mode failures.
- `agent-harness eval` includes a comparison eval that fails if an
  orchestration fixture lacks a baseline.

**First RED test**

- An integration test runs pack-level compare for `local-samples` and asserts
  the suite artifact links to every per-case comparison result and preserves
  failed or skipped modes.

### What to build

Add pack-level orchestration comparison, suite artifact writing, eval coverage,
and documentation updates that describe comparison as local evidence rather
than public benchmark comparability.

### Acceptance criteria

- [ ] Pack-level compare writes a suite artifact.
- [ ] Suite artifacts link to all per-case comparison artifacts.
- [ ] Per-case failures remain inspectable and are not collapsed into a vague
      aggregate status.
- [ ] Eval coverage enforces the baseline requirement.
- [ ] Docs state that role-count expansion requires comparison evidence and
      that explicit broader-pack allowlists remain roadmap scope.

### Out of scope

- External benchmark datasets.
- Configurable benchmark allowlists.
- Release-readiness hard gates unless a later release plan requires them.

## Cross-Phase Invariants

- Every orchestration fixture is compared against a single-agent baseline.
- Baseline failure blocks valid orchestration comparison for that case.
- Existing `benchmark run` and `benchmark_result.v1` behavior remains
  compatible.
- Orchestration remains sequential.
- Child runs do not share raw memory.
- Downstream children receive only policy-filtered generated handoffs.
- Benchmark comparison never widens policy, tools, paths, provider use, or
  approvals.
- Supervisor approval never implies child mutation approval.
- Tester mode requires real executable test commands.
- Dry-run skipped tests are not counted as passed tests.
- Token/runtime/cost values are unavailable unless supported by evidence.
- Recommendations are evidence-only and never mutate defaults.
- Tests verify public CLI behavior and persisted artifacts, not private helper
  names.
