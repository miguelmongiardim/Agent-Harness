# Template Pack System

## Status

V7 is the planned `v1.4.0` template-pack track. The durable source documents
are the [V7 PRD](prd-agent-harness-v7.md) and
[V7 implementation plan](../plans/agent-harness-v7.md).

Phase 0 documents the local-first scope and adds docs-check guards before
manifest loading, source discovery, rendering, dry-run, preview, or apply
behavior changes land.

## Current Capabilities

The current implementation provides a bundled local template catalog. It can
list, show, validate, and apply packaged templates through the existing
`agent-harness template` commands. The stable template IDs are `python-lib`,
`cli-tool`, and `fastapi-service`, and legacy bundled JSON inputs remain
readable through the current compatibility path.

Clean empty-destination scaffolding is local. Non-empty targets, overwrites,
and unsupported template capabilities remain guarded by policy and approval
planning.

## V7 Local Pack Boundary

V7 keeps template ownership in `agent_harness.templates` and deepens that
boundary around local template packs. The target behavior is:

- `template.v2.toml` pack manifests loaded with `tomllib`
- bundled template packs plus legacy bundled JSON readability
- explicit local pack directories from `config.v2` `templates.local_dirs`
- deterministic `{{ param_name }}` substitution in declared text files and
  declared relative target paths
- dry-run and preview-diff planning with no target or evidence mutation
- clean empty-target apply without approval after validation and policy checks
- `template_application.v1` evidence for actual applies
- release-readiness gates for bundled pack validation, dry-run, clean apply,
  generated schema validation, docs presence, and evidence presence

The preferred future apply option is `--target`; `--destination` remains a
compatibility alias.

## Guarded Scope

The V7 docs-check guard rejects implemented-scope claims that template packs
already provide remote catalogs, marketplace behavior, signing, organization
catalogs, cloud registries, hook execution, script execution, enterprise
governance, or conditional file inclusion.

Those phrases are valid only in roadmap, out-of-scope, not-implemented, or
future sections, or when the sentence explicitly denies support.

## Roadmap / Not Implemented Yet

Remote template catalogs, template marketplace behavior, template signing,
organization template catalogs, cloud template registries, enterprise template
governance, hook execution, script execution, arbitrary lifecycle hooks,
conditional file inclusion, full template programming, `template create`,
`template export`, and `eval.v2` remain outside the V7 implementation target.
