# agent_harness.orchestration

## Purpose

`agent_harness.orchestration` owns policy-gated multi-child orchestration over
normal Agent Harness runs. It loads `orchestration.v1` specs, validates explicit
orchestration policy, materializes child `task.v2` files, runs children in
deterministic dependency order, records aggregate evidence, and supports
approval-bound resume.

Orchestration is a supervisor over the native runtime, not a separate runtime.
Child runs still use `HarnessRuntime`, normal task schemas, normal policy
evaluation, normal provider gates, normal tool approvals, and normal run
artifacts.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Orchestration spec, child, summary, event, manifest, approval, handoff, export, and child-run schemas. |
| `specs.py` | Loads and validates orchestration specs from disk. |
| `policy.py` | Enforces denial-first orchestration policy and role ceiling requirements. |
| `store.py` | Manages orchestration artifact directories, events, summaries, manifests, child records, approvals, and handoffs. |
| `runner.py` | Implements run, inspect, export, approve, and resume flows for orchestrations. |
| `__init__.py` | Exports the public orchestration API and schema classes. |

## Execution Flow

1. Load and validate an orchestration spec.
2. Require explicit `policy.v2.orchestration` enablement before child launch.
3. Sort children by dependencies and materialize each child task.
4. Inject generated handoffs from direct dependencies as policy-mediated
   generated context.
5. Delegate child execution to the native runtime.
6. Stop and record blocked state when a child pauses, fails, or requires a
   supervisor approval.
7. Resume only when the stored approval binding matches the pending plan.

## Boundaries

Do not add child behavior that bypasses normal runtime, policy, provider, or
tool approval gates. MCP exposure of orchestration artifacts belongs in
`agent_harness.mcp`; release gates belong in `agent_harness.release`.
