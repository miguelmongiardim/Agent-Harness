---
schema_version: skill.v1
skill_id: prd-to-plan
name: PRD to Plan
version: 1.0.0
description: Turn a PRD into a multi-phase implementation plan using tracer-bullet vertical slices, saved as a Markdown file in ./plans/ or equivalent planning location. Use when the user wants to break down a PRD, create an implementation plan, plan phases from a PRD, or mentions tracer bullets.
category: planning
compatible_agent_harness_versions: ">=1.5.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
output_artifacts:
  - implementation_plan
---

# PRD to Plan

Break a PRD into a phased implementation plan using vertical slices.

A vertical slice is a narrow but complete path through the system that can be tested, demonstrated, and reviewed independently.

The output should be a Markdown plan, usually saved in `./plans/` or another agreed planning location.

## Process

### 1. Confirm the PRD is in context

The PRD should already be available in the conversation, repository, issue tracker, or provided document.

If it is not available, ask the user to provide it.

Do not invent a plan without a PRD unless the user explicitly wants a draft plan from rough notes.

### 2. Explore available implementation context

Explore any available codebase or project context to understand:

- current architecture
- existing patterns
- public interfaces
- test style
- integration layers
- storage model
- configuration model
- operational constraints
- security or policy constraints

If this is a greenfield project, make that explicit and define the intended architecture boundaries.

### 3. Identify durable architectural decisions

Before slicing, identify high-level decisions that are unlikely to change throughout implementation.

Examples:

- public interface shape
- CLI command shape
- API route structure
- database schema shape
- key data models
- storage model
- runtime boundary
- policy boundary
- authentication or authorization approach
- approval model
- audit model
- third-party service boundary
- local versus remote execution boundary

These durable decisions go in the plan header so every phase can reference them.

### 4. Draft vertical slices

Break the PRD into tracer-bullet phases.

Each phase must cut through the real system end-to-end.

Do not create horizontal infrastructure phases unless explicitly justified as a walking skeleton prerequisite.

Bad phase examples:

- build all schemas
- build database
- build CLI
- build retrieval
- build policy engine
- build all tests
- build all documentation

Good phase examples:

- user can run a task and inspect the resulting run artifact
- policy blocks a denied file from entering context
- patch action pauses for approval and resumes safely
- retrieved context is stored with provenance and sensitivity labels
- eval produces a scorecard from a completed run
- invalid configuration fails validation with actionable diagnostics

## Vertical Slice Rules

Each phase must satisfy these rules:

- deliver a narrow but complete behavior
- be demoable or verifiable on its own
- cut through every necessary integration layer
- include observable behaviors
- identify the first failing test to write
- include acceptance criteria
- state what is out of scope
- avoid fragile implementation details
- include only durable interface decisions

Prefer many thin slices over few thick slices.

Avoid dead architecture. A subsystem should not be implemented unless it is exercised by a behavior in the current or immediately following slice.

### Walking skeleton rule

For large systems, create a Phase 0 walking skeleton only if needed.

A walking skeleton should prove the smallest end-to-end path through the final architecture.

Example:

- parse a minimal spec
- apply minimal policy
- create a run id
- emit an audit event
- inspect the run

A walking skeleton is not permission to build horizontal infrastructure without behavior.

### 5. Present the proposed breakdown

Present the proposed phases as a numbered list.

For each phase show:

- title
- user stories covered
- observable behaviors
- first RED test
- acceptance criteria
- out of scope

Ask whether the granularity is too coarse, too fine, or correct.

Iterate until the breakdown is approved.

### 6. Write the plan

Write the plan as Markdown.

Use `./plans/<feature-name>.md` when working inside a repository, or another explicit planning location if global.

## Plan Template

# Plan: <Feature Name>

> Source PRD: <brief identifier, link, or filename>

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: ...
- **Key models**: ...
- **Schema**: ...
- **Storage**: ...
- **Runtime boundary**: ...
- **Policy boundary**: ...
- **Approval model**: ...
- **Audit model**: ...
- **External service boundary**: ...

---

## Phase 0: <Walking Skeleton Title, if needed>

**User stories covered**

- ...

**Observable behaviors**

- ...

**First RED test**

- ...

### What to build

Describe the smallest full path through the intended architecture.

### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Out of scope

- ...

---

## Phase 1: <Title>

**User stories covered**

- ...

**Observable behaviors**

- ...

**First RED test**

- ...

### What to build

Describe the end-to-end behavior, not a layer-by-layer checklist.

### Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Out of scope

- ...

---

## Phase 2: <Title>

**User stories covered**

- ...

**Observable behaviors**

- ...

**First RED test**

- ...

### What to build

...

### Acceptance criteria

- [ ] ...

### Out of scope

- ...

## Cross-Phase Invariants

List invariants that every phase must preserve.

Examples:

- no subsystem bypasses the policy engine
- all external effects are auditable
- denied data never enters context
- approvals are bound to the exact proposed effect
- tests verify behavior through public interfaces
- no roadmap feature is implemented without a testable behavior
