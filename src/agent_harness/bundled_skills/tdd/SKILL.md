---
schema_version: skill.v1
skill_id: tdd
name: Test-Driven Development
version: 1.0.0
description: Guide implementation through red, green, and refactor cycles.
category: implementation
compatible_agent_harness_versions: ">=1.4.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
output_artifacts:
  - implementation_notes
---

# Test-Driven Development

Use this workflow when a behavior change should be developed from a public
failing example first. Select one observable behavior, write a focused
expectation for that behavior, make the smallest implementation change that
satisfies it, and clean up only after the behavior is green.

Tests should verify public behavior and persisted evidence instead of private
helper names. Repeat the cycle until the phase acceptance criteria are covered.
