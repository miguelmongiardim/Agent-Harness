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

## Migration Notes From v0.3.0 To v1.0.0

v1.0.0 keeps the v0.3.0 schemas as the public compatibility baseline:
`config.v2`, `task.v2`, `policy.v2`, and `template.v2`. Existing readable v0.2.0
inputs remain compatibility inputs through the migration workflow, but new
projects and bundled examples continue to emit v0.3.0 schemas.

No workspace rewrite is required for a v0.3.0 workspace that already uses the
v0.3.0 defaults. Maintainers should run:

```powershell
agent-harness migrate schemas
agent-harness docs check
agent-harness doctor
```

Use `agent-harness migrate schemas --write` only for deterministic safe
config, task, and policy upgrades after reviewing the report. The command does
not silently broaden permissions, template capabilities, provider-input
handling, or retrieval behavior.

The v1.0.0 release changes release discipline rather than adding enterprise or
platform scope. Docker packaging is for local/demo reproducibility, and
production deployment, compliance readiness, MCP support, multi-agent support,
external catalogs, and production Qdrant server mode remain roadmap work.

## Roadmap

Loose policy rewrites, external catalog migration, and broad non-Python template
migration are outside the current release.
