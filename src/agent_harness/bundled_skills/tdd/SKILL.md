---
schema_version: skill.v1
skill_id: tdd
name: Test-Driven Development
version: 1.0.0
description: Test-driven development with red-green-refactor loop. Use when the user wants to build features or fix bugs using TDD, mentions red-green-refactor, wants integration tests, or asks for test-first development.
category: implementation
compatible_agent_harness_versions: ">=1.5.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
output_artifacts:
  - implementation_notes
---

# Test-Driven Development

## Philosophy

Core principle: tests should verify behavior through public interfaces, not implementation details.

Code can change entirely. Tests should not.

Good tests are integration-style. They exercise real code paths through public APIs. They describe what the system does, not how it does it.

A good test reads like a specification.

Bad tests are coupled to implementation. They mock internal collaborators unnecessarily, test private methods, or verify through external means instead of the public interface.

Warning sign: a test breaks during refactor even though behavior has not changed.

## PRD / Plan Integration

When a PRD and implementation plan exist, do not invent tests independently.

For each vertical slice:

1. Read the relevant PRD user stories.
2. Read the phase acceptance criteria.
3. Select one observable behavior.
4. Write one failing test for that behavior.
5. Implement the minimum code to pass.
6. Repeat until the phase acceptance criteria are satisfied.
7. Refactor only after tests are green.

Do not write all tests for the phase upfront.

Do not test schema shape unless schema validation is itself the observable behavior.

Do not test private functions.

## Anti-Pattern: Horizontal Slices

Do not write all tests first, then all implementation.

This is horizontal slicing.

Wrong:

```text
RED:   test1, test2, test3, test4, test5
GREEN: impl1, impl2, impl3, impl4, impl5
```

Right:

```text
RED -> GREEN: test1 -> impl1
RED -> GREEN: test2 -> impl2
RED -> GREEN: test3 -> impl3
```

Tests written in bulk often test imagined behavior instead of real behavior.

Correct approach: vertical slices through tracer bullets.

One test. One implementation. Repeat.

## Workflow

### 1. Planning

Before writing code:

- confirm the public interface
- confirm the behavior to test
- identify opportunities for deep modules
- design interfaces for testability
- list behaviors to test, not implementation steps
- prioritize critical paths and complex logic

Ask:

- What is the public interface?
- What observable behavior matters most?
- What would prove this slice works?

### 2. Tracer Bullet

Write one test that confirms one behavior.

```text
RED:   Write test for first behavior -> test fails
GREEN: Write minimal code to pass -> test passes
```

This proves the path works end-to-end.

### 3. Incremental Loop

For each remaining behavior:

```text
RED:   Write next test -> fails
GREEN: Minimal code to pass -> passes
```

Rules:

- one test at a time
- only enough code to pass the current test
- do not anticipate future tests
- keep tests focused on observable behavior
- do not test private implementation details
- do not add speculative features

### 4. Refactor

After all tests pass, look for refactor candidates:

- extract duplication
- deepen modules
- move complexity behind simple interfaces
- apply SOLID principles where natural
- rename for clarity
- simplify public interfaces
- remove dead code
- run tests after each refactor step

Never refactor while RED.

## What to Test

Prioritize:

- public behavior
- critical paths
- complex logic
- risky boundaries
- security or policy invariants
- persistence behavior visible through public interfaces
- error behavior visible to users
- regression cases discovered during development

Do not prioritize:

- private helper functions
- internal data structure shape
- mocks of every collaborator
- implementation order
- incidental logging text unless it is part of a public contract

## Mocking Rules

Mock external systems only when necessary.

Prefer real code paths for:

- domain logic
- policy decisions
- validation
- storage adapters when cheap
- CLI/API integration behavior

Mocks are acceptable for:

- external paid APIs
- slow services
- nondeterministic model calls
- network dependencies
- destructive side effects

When mocking, mock at the system boundary, not inside the implementation.

## Checklist Per Cycle

```text
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative feature added
[ ] Test maps to PRD behavior or plan acceptance criterion
[ ] Refactor happens only after GREEN
```

## Output Per TDD Cycle

```md
## TDD Cycle: <behavior>

### Behavior

<observable behavior under test>

### RED

<test added and why it fails>

### GREEN

<minimal implementation added>

### Refactor

<refactor performed, or "none">

### Result

<test result>
```
