# agent_harness.runtimes

## Purpose

`agent_harness.runtimes` owns runtime adapter selection shims around the native
runtime. It provides compatibility exports for the normal harness runtime and
small optional adapter proofs that demonstrate how alternate orchestration
frameworks can delegate to the same policy and evidence boundaries.

The native execution implementation lives in `agent_harness.core.runtime`.

## Key Files

| File | Role |
| --- | --- |
| `native.py` | Re-exports `HarnessRuntime` and `approve_action` from the native core runtime. |
| `langgraph_adapter.py` | Optional LangGraph adapter proof that lazy-loads `langgraph`, delegates the covered run path to the native runtime, and records adapter selection evidence. |
| `mcp_adapter.py` | Optional MCP runtime-adapter boundary that fails clearly for unsupported runtime behavior. |
| `plan_act_observe.py` | Plan-act-observe runtime schema/flow helpers. |
| `schema.py` | Runtime adapter evidence schema. |
| `__init__.py` | Lazily exports the public runtime names. |

## Boundaries

Adapters must reuse the normal policy, storage, context, provider, and tool
paths. They should not create a second implementation of approval binding,
context assembly, provider access, or run evidence.
