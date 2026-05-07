# agent_harness.core

## Purpose

`agent_harness.core` owns the native runtime implementation and compatibility
exports for deterministic model behavior. It is the orchestration center for a
single harness run: load public inputs, assemble context, ask the deterministic
or provider-backed model for actions, evaluate those actions through policy,
execute tools, write evidence, and summarize the run.

This package coordinates other boundaries, but it should not absorb their
details. Policy evaluation stays in `policy`, tool implementations stay in
`tools`, context construction stays in `context`, provider envelope handling
stays in `model`, and append-only artifacts stay in `storage`.

## Key Files

| File | Role |
| --- | --- |
| `runtime.py` | Implements `HarnessRuntime` and `approve_action`, including run setup, policy/config/task loading, context assembly, provider-use binding, action execution, approvals, checkpoints, template application, git commit planning, summaries, and event evidence. |
| `models.py` | Compatibility exports for `DeterministicMockModel` and `ModelClient`. |
| `interfaces.py` | Compatibility export for the model client protocol. |
| `checkpoints.py` | Compatibility export for checkpoint schema. |
| `exceptions.py` | Shared harness exception classes, including `UnsupportedAdapterError` for optional adapter boundaries. |
| `__init__.py` | Public compatibility exports for deterministic model and model client names. |

## Runtime Responsibilities

`HarnessRuntime.run_task()` is the main local execution path. It creates run
storage, records schema evidence, builds context, evaluates provider permissions,
executes model-requested tool calls, records checkpoints and events, writes
approval records when needed, and returns a `RunSummary`.

The runtime also coordinates dry runs, template application planning, generated
handoffs from orchestration, skill manifests, provider-input manifests, optional
runtime adapters, and security advisory collection.

## Boundaries

Keep `runtime.py` focused on sequencing and evidence binding. If new behavior
needs its own schema, storage format, validation rules, renderer, retriever,
provider transport, or policy decision, put that behavior in the owning package
and have the runtime call it.
