# Schema Migration

## Current Capabilities

`agent-harness migrate schemas` is the public schema migration workflow.

By default, it runs in report mode and does not mutate files. Reports include:

- original schema version
- proposed effective schema version
- changed and unchanged fields
- warnings
- unsupported upgrade reasons

`agent-harness migrate schemas --write` rewrites only deterministic safe
upgrades for config, task, and policy files. It preserves or tightens policy
behavior and does not widen provider-input permissions or template
capabilities. Template v1 inputs are reported through compatibility paths rather
than silently rewritten.

## Roadmap

Loose policy rewrites, external catalog migration, and broad non-Python template
migration are outside the current release.
