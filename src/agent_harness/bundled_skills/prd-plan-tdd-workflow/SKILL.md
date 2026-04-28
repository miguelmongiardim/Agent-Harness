---
schema_version: skill.v1
skill_id: prd-plan-tdd-workflow
name: PRD Plan TDD Workflow
version: 1.0.0
description: Coordinate PRD, plan, and TDD guidance for feature work.
category: workflow
compatible_agent_harness_versions: ">=1.4.0,<2.0.0"
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

# PRD Plan TDD Workflow

Use this workflow when a feature should move from requirements to vertical
planning to incremental implementation. First clarify the product requirement,
then break it into observable slices, then implement each slice with one
focused behavior at a time.

Keep requirements, plans, and implementation evidence connected. The plan
should identify the public behavior for each slice, and the implementation
notes should record the red, green, and refactor result for each cycle.
