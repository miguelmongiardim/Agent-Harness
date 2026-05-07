# agent_harness.bundled_skills

## Purpose

`agent_harness.bundled_skills` stores the Markdown skill guidance that ships
with Agent Harness. These files are workflow instructions consumed by
`agent_harness.skills`; they are not executable plugins, tools, policies, or
templates.

Each skill directory contains a `SKILL.md` file with frontmatter and guidance
body text. The skills package validates that metadata, renders skill text for
inspection, resolves task-requested and template-recommended skills, and records
accepted or rejected skill context in run evidence.

## Current Bundled Skills

| Directory | Role |
| --- | --- |
| `write-a-prd` | Guides product-requirements discovery and drafting. |
| `prd-to-plan` | Turns PRDs into implementation plans. |
| `prd-plan-tdd-workflow` | Coordinates PRD, planning, and TDD execution flow. |
| `tdd` | Guides red-green-refactor implementation work. |

## Boundaries

Bundled skills may provide instructions and context only. They must not grant
additional tool authority, loosen policy, or imply execution capability. Policy
and context assembly decide whether skill content enters a run manifest.

When adding or editing a bundled skill, update the Markdown source and validate
it through the `skills` package instead of adding special cases in runtime code.
