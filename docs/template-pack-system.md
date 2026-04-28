# Template Pack System

## Status

V7 is the active `v1.4.0` template-pack track. The durable source documents are
the [V7 PRD](prd-agent-harness-v7.md) and
[V7 implementation plan](../plans/agent-harness-v7.md).

## Current Capabilities

The current implementation provides a bundled local template-pack catalog. It
can list, show, validate, dry-run, preview, and apply packaged templates through
the existing `agent-harness template` commands. The bundled V7 pack IDs are
`python-lib`, `cli-tool`, `fastapi-service`, `provider-audit`, and
`retrieval-quality`. Legacy bundled JSON inputs remain readable through the
compatibility model path, while the public bundled catalog now serves these IDs
from pack directories.

Clean empty-destination scaffolding is local and records
`template_application.v1` evidence plus workspace metadata. Non-empty targets,
overwrites, unsupported template capabilities, invalid packs, target escapes,
and undeclared parameters remain guarded before writing.

Every bundled V7 pack includes `template.v2.toml`, README content, demo
metadata, generated config/policy/task/eval examples, and at least one local
validation or demo command where practical.

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
