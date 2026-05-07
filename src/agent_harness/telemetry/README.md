# agent_harness.telemetry

## Purpose

`agent_harness.telemetry` owns small deterministic telemetry helpers used by
runtime, storage, reports, and tests. It provides consistent event payloads,
logger names, and trace IDs without introducing an external telemetry backend.

## Key Files

| File | Role |
| --- | --- |
| `events.py` | Builds event payload dictionaries in a consistent shape. |
| `logging.py` | Produces logger names for package-local logging. |
| `tracing.py` | Builds deterministic trace identifiers. |
| `__init__.py` | Exports `event_payload`, `logger_name`, and `trace_id`. |

## Boundaries

Telemetry helpers should stay side-effect-light and local. Do not add networked
metrics, analytics, or background reporting here. Durable run evidence belongs
in `storage`.
