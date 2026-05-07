# agent_harness.templates

## Purpose

`agent_harness.templates` owns bundled and local template catalog behavior. It
loads template records, reads `template.v2.toml` manifests, validates packs,
resolves parameters, renders declared files, plans apply operations, records
application evidence, and keeps non-empty targets or overwrites approval-bound.

Template code is responsible for deterministic scaffolding behavior. Runtime and
policy coordinate when a template can be applied, but parsing and rendering
rules belong here.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Template registry, detail, spec, parameter, write, apply, validation, and application evidence schemas. |
| `registry.py` | Lists bundled and configured local templates, reads registry metadata, detects unregistered bundled packs, and enforces unique template IDs. |
| `store.py` | Provides package-data access to bundled templates, registry files, manifests, and source metadata. |
| `validation.py` | Validates template packs, manifests, generated files, compatibility, capabilities, and diagnostics. |
| `apply.py` | Resolves parameters, renders files, builds preview diffs, plans writes, redacts previews, and creates template application evidence. |
| `__init__.py` | Lazily exports listing, loading, record loading, and apply planning functions. |

## Apply Flow

1. Load a template record from bundled or configured local sources.
2. Validate manifest compatibility and required capabilities.
3. Resolve parameters and render declared files.
4. Build a write plan and preview diffs.
5. Let runtime/policy require approval for non-empty targets or overwrites.
6. Write declared files only and persist `template_application.v1` evidence.

## Boundaries

Templates should not execute code, call providers, modify undeclared files, or
adjust policy. Template recommendations for skills remain recommendations; the
`skills` and `context` boundaries decide how guidance is resolved and included.
