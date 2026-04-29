---
schema_version: skill.v1
skill_id: prd-plan-tdd-workflow
name: PRD Plan TDD Workflow
version: 1.0.0
description: Coordinate PRD, vertical-slice planning, and red-green-refactor implementation. Use when starting a serious feature or project that should be built from product requirements through TDD execution.
category: workflow
compatible_agent_harness_versions: ">=1.5.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
related_skills:
  - write-a-prd
  - prd-to-plan
  - tdd
output_artifacts:
  - product_requirements_document
  - implementation_plan
  - implementation_notes
---

# PRD -> Plan -> TDD Workflow

Use this skill when building a non-trivial system from scratch or implementing a major feature.

This is a global workflow skill. It is not tied to a specific repository.

## Core Rule

Do not jump directly from PRD to code.

Use this sequence:

1. Write or confirm the PRD.
2. Convert the PRD into vertical tracer-bullet phases.
3. For each phase, execute TDD one observable behavior at a time.

## Why This Exists

Complex systems fail when product thinking, architecture, and implementation are disconnected.

This workflow keeps them connected:

- the PRD defines the product and system boundary
- the plan turns that boundary into vertical slices
- TDD proves each slice through observable behavior
- refactoring improves the design only after behavior is protected

## Workflow

### 1. PRD

Use `write-a-prd`.

The PRD must define:

- problem statement
- solution
- user stories
- behavioral requirements
- implementation decisions
- testing decisions
- out of scope
- major risks

The PRD should define the product and system boundary.

It should not become a low-level implementation checklist.

### 2. Plan

Use `prd-to-plan`.

The plan must be sliced vertically.

A valid phase proves an end-to-end behavior.

Bad phase examples:

- build all schemas
- build database
- build CLI
- build all retrieval
- build all policy
- build all documentation
- build all tests

Good phase examples:

- user can create a task run and inspect its artifacts
- denied files cannot enter a context pack
- risky patch action pauses for approval
- approved patch applies only if file hash still matches
- eval produces a scorecard from a completed run
- invalid configuration fails with actionable diagnostics

### 3. TDD Execution

Use `tdd`.

For each phase:

- choose one behavior
- write one failing test
- implement the minimum code
- get green
- repeat
- refactor only when green

## Non-Negotiables

- Do not write all tests upfront.
- Do not implement horizontal infrastructure before a vertical behavior needs it.
- Do not allow roadmap features to enter the implementation without a testable behavior.
- Do not test implementation details.
- Do not create dead architecture.
- Every subsystem must be exercised by at least one behavior test before it is considered part of the system.
- Every major PRD behavior must map to at least one test or explicit out-of-scope decision.
- Every phase must be demoable, inspectable, or verifiable.
- Refactor only when tests are green.

## Slice Output Template

For every implementation slice, produce:

```md
## Slice: <name>

### PRD user stories covered

- ...

### Behavior under test

- ...

### First RED test

- ...

### GREEN implementation scope

- ...

### Refactor candidates

- ...

### Acceptance criteria

- [ ] ...
```

## Completion Criteria

A slice is complete only when:

- its public behavior works
- its tests are green
- its acceptance criteria are satisfied
- no safety, policy, or architectural invariant is bypassed
- the implementation has no dead architecture
- refactor candidates were considered
- documentation is updated if the public behavior changed

## Global Project Completion Criteria

A project or major feature is complete only when:

- PRD user stories are implemented or explicitly deferred
- plan phases are complete or explicitly deferred
- behavioral tests exist for critical paths
- all tests pass
- public docs reflect actual behavior
- no documentation claims unsupported features
- roadmap items are clearly separated from implemented capabilities
