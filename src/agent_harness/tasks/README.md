# agent_harness.tasks

## Purpose

`agent_harness.tasks` owns the public task contract. A task describes the local
work the harness should perform: intent, target paths, context sources,
retrieval queries, allowed tools, max steps, test commands, template
application, skill requests, provider configuration, and related execution
inputs.

The task schema is a public surface. Changes to it affect CLI behavior, runtime
execution, demos, evals, benchmark packs, and compatibility migration.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Defines `TaskSpec` and task-level validators for schema version, IDs, paths, tools, templates, tests, providers, and skills. |
| `__init__.py` | Package marker for the task contract boundary. |

## Boundaries

Tasks declare requested behavior; they do not grant authority by themselves.
Policy profiles and runtime approval binding still control tool access, write
paths, provider use, template writes, generated context, and commits.
