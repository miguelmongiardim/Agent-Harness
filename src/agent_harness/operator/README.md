# agent_harness.operator

## Purpose

`agent_harness.operator` owns the local loopback operator API and packaged static
UI for inspecting existing Agent Harness evidence. It provides read-oriented
views over runs, policies, context manifests, approvals, governance exports, and
evidence packs, plus local approval/deny decisions that delegate to the existing
approval service.

The operator boundary sits above storage, policy, approvals, exports, provider
evidence, and run artifacts. It is not a runtime, arbitrary file server,
provider client, or hosted web platform.

## Key Files

| File | Role |
| --- | --- |
| `app.py` | FastAPI app factory, route definitions, token checks, loopback host checks, run/evidence readers, approval endpoints, and static UI serving. |
| `schema.py` | Operator response schemas and API contract models. |
| `static/` | Packaged HTML, CSS, and JavaScript for the browser UI. |
| `__init__.py` | Lazily exports `create_operator_app`. |

## API Shape

The app exposes health, run listing/detail, context manifest inspection, policy
inspection, artifact status reporting, approvals, governance exports, and
evidence pack views over existing local artifacts. It is intended to be served
on loopback hosts with a token.

## Boundaries

Operator code may read known artifact paths through the owning storage and
evidence abstractions. It should not browse arbitrary files, trigger provider
calls, generate evidence packs implicitly, mutate run summaries, or create new
execution surfaces.
