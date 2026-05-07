# agent_harness.evidence

## Purpose

`agent_harness.evidence` owns the review-only evidence pack boundary. It
collects existing local governance and release evidence into canonical pack
files, indexes, findings, control mappings, manifests, optional archives, and
check results.

This package does not certify a system, make legal determinations, or generate
the governance domains it depends on. It packages and validates existing local
evidence so a reviewer can inspect what is present, missing, malformed, blocked,
or excluded.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Evidence pack, manifest, index, findings, control mapping, check result, diagnostic, and export result schemas. |
| `checks.py` | Prerequisite and pack validation checks, including required governance export detection and blocking finding handling. |
| `pack.py` | Builds evidence state, writes canonical JSON/Markdown files, filters unsafe artifact references, computes checksums, and optionally creates archives. |
| `__init__.py` | Exports evidence pack construction, prerequisite checks, validation checks, constants, and public schemas. |

## Pack Files

The bundle writer can produce:

- `evidence_pack.v1.json`
- `evidence_manifest.v1.json`
- `evidence_index.v1.json`
- `evidence_findings.v1.json`
- `control_mapping.v1.json`
- Markdown renderings for review-oriented formats
- optional archive output when requested

## Boundaries

Evidence pack code reads configured artifact roots and safe governance outputs.
It should not browse arbitrary files, include raw provider payloads, include
private upload references, regenerate governance aggregation, mutate policy, or
perform release actions. Validation failures should be recorded as evidence
findings or diagnostics rather than hidden.
