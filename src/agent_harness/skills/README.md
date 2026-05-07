# agent_harness.skills

## Purpose

`agent_harness.skills` owns reusable Markdown skill guidance. It discovers
bundled and configured local skills, parses frontmatter, validates skill files,
renders skill bodies, resolves task/template skill requests, and builds
`skill_manifest.v1` run evidence after context assembly.

Skills are guidance artifacts. They are not tools, executable code, provider
profiles, templates, policy files, or approval records.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Skill spec, validation report, registry record, detail, resolution record, and manifest schemas. |
| `validation.py` | Lists skills, validates bundled/local skills, parses frontmatter and a small YAML subset, renders skill details, and reports diagnostics. |
| `resolution.py` | Resolves task-requested and template-recommended skills into accepted, missing, duplicate, or incompatible resolution records. |
| `manifest.py` | Builds run skill manifests from resolution records and context manifest inclusion/rejection evidence. |
| `__init__.py` | Lazily exports the public skill API. |

## Skill Flow

1. Skill records are discovered from bundled package data and configured local
   skill directories.
2. Validation checks metadata, body structure, compatibility, content markers,
   and authority boundaries.
3. Resolution combines explicit task requests with template recommendations.
4. Runtime asks context assembly whether resolved skill guidance may be included
   under policy.
5. `build_skill_manifest()` records what was requested, included, rejected, and
   linked to context manifest item IDs.

## Boundaries

Skill content must not grant authority. Policy controls whether skill guidance
enters context, and task/policy ceilings still control tools, provider use, and
write access.
