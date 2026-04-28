---
schema_version: skill.v1
skill_id: write-a-prd
name: Write a PRD
version: 1.0.0
description: Guide a user from product intent to testable product requirements.
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

Use this workflow when a user wants to define a non-trivial feature before
implementation. Start from the intended user outcome, clarify the current
system boundary, identify observable behavior, and turn the result into
testable requirements.

The output should distinguish implemented behavior, planned behavior, explicit
non-goals, user stories, behavioral requirements, implementation decisions, and
testing decisions. Keep requirements tied to public interfaces and observable
effects rather than private implementation details.
