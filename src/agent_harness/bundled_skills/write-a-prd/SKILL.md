---
schema_version: skill.v1
skill_id: write-a-prd
name: Write a PRD
version: 1.0.0
description: Create a PRD through user interview, context exploration, module design, and testable behavioral requirements. Use when the user wants to write a PRD, create a product requirements document, define a feature, or plan a non-trivial system.
category: planning
compatible_agent_harness_versions: ">=1.5.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
output_artifacts:
  - product_requirements_document
---

# Write a PRD

This skill defines the product boundary, user-facing behavior, implementation constraints, and testing direction before implementation begins.

Use it for non-trivial systems or features where the cost of unclear requirements would be higher than the cost of writing a short but rigorous PRD.

You may skip steps only when they are clearly unnecessary.

## Process

### 1. Understand the problem

Ask the user for a detailed description of:

- the problem they want to solve
- who the users or actors are
- what current workflow or pain exists
- what success would look like
- what constraints exist
- what they already know about possible solutions
- what is explicitly not desired

Do not jump to implementation before the problem boundary is clear.

### 2. Explore available context

Explore any available codebase, documents, examples, architecture notes, or prior discussion relevant to the feature.

Use this to verify assumptions and understand:

- current architecture
- existing workflows
- available public interfaces
- current test patterns
- relevant constraints
- integration points
- operational or security requirements

If no codebase exists yet, treat this as a greenfield PRD and make that explicit.

### 3. Interview the user

Clarify every important branch of the design tree until there is a shared understanding.

Resolve:

- core workflows
- user roles
- success criteria
- failure modes
- approval or review points
- data boundaries
- security boundaries
- integration boundaries
- implementation constraints
- what belongs in v0.1.0 versus later versions

Do not ask low-value questions that can be resolved by sensible defaults.

### 4. Identify deep modules

Sketch the major modules that will need to exist or change.

Actively look for opportunities to extract deep modules.

A deep module encapsulates substantial functionality behind a simple, stable, testable interface.

Good deep modules:

- hide complexity
- expose a small public interface
- are independently testable
- reduce coupling
- are unlikely to change their public contract often

Avoid shallow modules that merely wrap one line of code or mirror implementation details.

### 5. Identify testable behaviors

Before writing the PRD, identify the behaviors that must later become TDD acceptance tests.

A behavior is externally observable through a public interface.

Examples:

- a user can create a task run from a valid task specification
- a denied file cannot enter a context pack
- a risky action pauses for approval
- a completed run emits an audit trail
- an invalid configuration is rejected with a clear error

Do not define tests against private functions or internal implementation shape.

### 6. Confirm testing direction

Confirm:

- which behaviors are highest risk
- which behaviors need integration tests
- which behaviors need adversarial tests
- which modules should be tested through their public interface
- which parts are deliberately out of scope for this PRD

### 7. Write the PRD

Use the PRD template below.

The PRD should be precise enough to generate a vertical-slice implementation plan.

The PRD should not become a low-level file-by-file implementation checklist.

## Architecture and TDD Alignment

Before writing the PRD, identify:

- the core system boundary
- the primary user-facing or system-facing workflows
- the deep modules that should hide complexity behind stable interfaces
- the behaviors that must later become TDD acceptance tests
- the behaviors that are explicitly out of scope for the first implementation

Do not turn implementation tools into requirements.

Tools, frameworks, databases, libraries, or vendors may be listed as implementation decisions only if they directly support a user-facing or system-facing requirement.

Every major user story should be written so it can later be mapped to at least one observable behavior test.

## PRD Template

# PRD: <Feature or System Name>

## Problem Statement

Describe the problem from the user's perspective.

Include:

- current pain
- why it matters
- what breaks or remains inefficient without this feature
- who is affected

## Solution

Describe the proposed solution from the user's perspective.

Include:

- core workflows
- expected user experience
- system behavior
- important constraints
- what the solution deliberately avoids

## User Stories

Provide a numbered list of user stories.

Each user story should use this format:

1. As a <actor>, I want a <feature>, so that <benefit>.

User stories should cover:

- primary happy paths
- error paths
- review/approval paths
- operational or maintenance paths
- security or governance paths, if relevant

## Behavioral Requirements

Provide a numbered list of externally observable behaviors the system must support.

Each behavior should be testable through a public interface.

Examples:

1. A user can create a run from a valid task specification and inspect the resulting run artifacts.
2. The system rejects invalid task specifications with clear validation errors.
3. Denied paths cannot enter generated context.
4. Risky actions pause for approval before execution.
5. Approved actions execute only if their approval binding still matches the proposed effect.

## Implementation Decisions

List implementation decisions that were made.

This can include:

- major modules to build or modify
- public interfaces to introduce or change
- architectural decisions
- schema decisions
- API or CLI contracts
- storage model
- security boundaries
- approval boundaries
- policy boundaries
- integration constraints
- selected technologies and why they are justified

Do not include fragile implementation details likely to change quickly, such as exact private function names.

## Testing Decisions

List testing decisions.

Include:

- what makes a good test for this feature
- which behaviors must be tested
- which modules should be tested through public interfaces
- which risks require adversarial or regression tests
- which tests define initial acceptance
- relevant prior test patterns, if any

Tests should verify behavior through public interfaces, not implementation details.

## Out of Scope

List what is explicitly not part of this PRD.

Include:

- deferred features
- unsupported workflows
- integrations not included
- shortcuts that are intentional
- future roadmap items

## Further Notes

Add any additional notes about:

- tradeoffs
- risks
- open questions
- research background
- migration concerns
- operational concerns
- future roadmap
