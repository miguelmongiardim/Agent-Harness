---
schema_version: skill.v1
skill_id: prd-to-plan
name: PRD to Plan
version: 1.0.0
description: Convert product requirements into vertical implementation slices.
category: planning
compatible_agent_harness_versions: ">=1.4.0,<2.0.0"
required_capabilities: []
allowed_context_classes:
  - public
  - internal
output_artifacts:
  - implementation_plan
---

# PRD to Plan

Use this workflow when a product requirements document needs to become an
implementation plan. Preserve the user stories and acceptance criteria, then
organize work into vertical slices that each produce observable behavior.

Each slice should name the public interface, the behavior to prove, the first
test expectation, the implementation boundary, and the evidence needed before
the slice can be considered complete.
