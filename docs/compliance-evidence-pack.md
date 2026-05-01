# Compliance Evidence Pack

## Status

The V1.9 Compliance Evidence Pack is in progress. The durable PRD lives in
[docs/prd-agent-harness-v1.9-compliance-evidence-pack.md](prd-agent-harness-v1.9-compliance-evidence-pack.md)
and the implementation plan lives in
[plans/agent-harness-v1.9-compliance-evidence-pack.md](../plans/agent-harness-v1.9-compliance-evidence-pack.md).

Through Phase 7, the `agent-harness evidence` CLI surface exposes `pack`,
`check`, and `index` commands. `pack`, `check`, and `index` validate the
required V12 governance export prerequisites and fail with exit code `2` when
they are missing, without generating governance exports.

When the V12 exports are present, `agent-harness evidence pack --format json`
writes canonical JSON evidence artifacts under the selected evidence output
directory:

- `evidence_pack.v1.json`
- `evidence_manifest.v1.json`
- `evidence_index.v1.json`
- `evidence_findings.v1.json`
- `control_mapping.v1.json`
- `checksums.sha256`

`agent-harness evidence pack --format bundle` and `--format markdown` also
write Markdown presentation files:

- `evidence_pack.v1.md`
- `control_mapping.v1.md`

Phase 3 redaction-filters artifact references from `governance_index.v1`.
Included artifacts must be normalized project-relative references and are
hash-indexed from the local file. Absolute paths, path traversal references,
raw provider payloads, private upload references, credential-like references,
and raw vector database internals are omitted with evidence findings instead
of being copied into pack contents. Optional absent evidence domains are
recorded as `not_present`.

Phase 6 packages safe domain summaries from `governance_summary.v1` into
`evidence_pack.v1`. Present domains can include safe summary metadata and
evidence refs for governance, policy, approvals, provider, retrieval,
templates, skills, MCP, multi-agent, supply-chain, security, docs claim, and
release-readiness evidence. Optional domains that V12 does not report remain
`not_present`. Malformed domain summary payloads are omitted, the domain is
marked `malformed_evidence`, and `evidence_findings.v1` records a
`malformed_domain_summary` finding instead of crashing pack generation.

The mapping uses internal review themes, safe evidence refs, limited coverage
statuses, limitations, and the non-certification disclaimer. Archive creation
is opt-in with `--archive`, which writes a zip under the evidence output
directory's `archive/` folder. `agent-harness evidence check` validates the
current in-memory pack state and existing pack findings: exit code `0` means
valid, `1` means blocking evidence findings exist, `2` means invalid input or
missing prerequisites, and `3` means an internal check error. The
`agent-harness evidence index` command prints the current `evidence_index.v1`
JSON.

The local operator API exposes token-protected read-only evidence routes backed
by existing evidence pack files:

- `GET /api/v1/evidence/overview`
- `GET /api/v1/evidence/packs`
- `GET /api/v1/evidence/packs/{pack_id}`
- `GET /api/v1/evidence/control-map`
- `GET /api/v1/evidence/artifact-index`
- `GET /api/v1/evidence/findings`

The routes require `X-Agent-Harness-Operator-Token`, read fixed evidence
artifact filenames under the configured evidence root, reject mutation methods,
and do not generate packs or expose raw provider payloads, secrets, absolute
paths, or arbitrary workspace files. Operator UI views and release-readiness
gates remain later-phase work.

## Planned Boundary

The planned evidence-pack boundary packages existing governance evidence into
portable review artifacts. It consumes completed V12 governance exports instead
of rebuilding governance aggregation, running tasks, calling providers, running
retrieval, executing scanners, applying templates, serving MCP, launching
orchestration children, or creating release evidence.

Required V12 prerequisite artifacts are:

- `governance_summary.v1`
- `governance_report.v1`
- `governance_index.v1`
- `governance_findings.v1`

If those exports are missing, current Phase 7 evidence commands fail clearly
and tell the user to generate V12 governance exports first.

## Claim Boundary

This evidence pack supports review and audit preparation.
It does not certify compliance with any legal, regulatory, security, or
organizational framework.

Future pack outputs must not imply certification, auditor approval, framework
conformance, control effectiveness, or legal readiness. JSON artifacts are the
planned canonical contract; Markdown is presentation only.

## Safety Boundary

Pack references are project-relative, normalized, hash-indexed where safe,
schema-versioned where applicable, and tagged with redaction status. Raw
provider payloads, credentials, API keys, environment values, raw headers,
private uploads, PII, customer data, secret values, absolute machine paths, raw
vector database internals, and arbitrary workspace files must not enter pack
outputs.
