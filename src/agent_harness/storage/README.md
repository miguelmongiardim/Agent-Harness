# agent_harness.storage

## Purpose

`agent_harness.storage` owns local run evidence persistence. It writes and reads
append-only run artifacts, JSONL event logs, approval records, checkpoints,
summaries, applied-template metadata, workspace metadata, and SQLite indexes
under the configured artifact root.

Storage is the durable audit boundary for runtime, tools, approvals,
orchestration, exports, governance, MCP resources, and evidence packs.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Checkpoint, approval, event, summary, applied-template, skill recommendation, and workspace metadata schemas. |
| `runs.py` | Implements `RunStore`, event appending, SQLite index initialization, action/approval/checkpoint/summary IO, metadata updates, and run lookup helpers. |
| `blobs.py` | Compatibility exports for JSON blob IO helpers. |
| `audit_store.py` | Compatibility export for `RunStore`. |
| `sqlite.py` | Compatibility export for `RunStore`. |
| `__init__.py` | Lazily exports `RunStore` and `make_event`. |

## Artifact Shape

A run store creates `.agent-harness/runs/<run-id>/` with action, approval, and
checkpoint subdirectories plus `events.jsonl` and `summary.json`. The artifact
root also contains `state.sqlite3`, which indexes runs, events, and approvals
for inspection without replacing the append-only files.

## Boundaries

Storage should not decide whether an action is allowed, render exports, or call
providers. It records the evidence produced by those packages and preserves
enough metadata for later inspection and validation.
