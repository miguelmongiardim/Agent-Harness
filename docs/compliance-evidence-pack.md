# Compliance Evidence Pack

## Status

The V1.9 Compliance Evidence Pack is in progress. The durable PRD lives in
[docs/prd-agent-harness-v1.9-compliance-evidence-pack.md](prd-agent-harness-v1.9-compliance-evidence-pack.md)
and the implementation plan lives in
[plans/agent-harness-v1.9-compliance-evidence-pack.md](../plans/agent-harness-v1.9-compliance-evidence-pack.md).

Phase 2 implements the `agent-harness evidence` CLI surface with `pack`,
`check`, and `index` commands. `pack` and `check` validate the required V12
governance export prerequisites and fail with exit code `2` when they are
missing, without generating governance exports.

When the V12 exports are present, `agent-harness evidence pack --format json`
writes the first canonical JSON evidence artifacts under the selected evidence
output directory:

- `evidence_pack.v1.json`
- `evidence_manifest.v1.json`
- `evidence_index.v1.json`
- `evidence_findings.v1.json`
- `checksums.sha256`

Markdown presentation, archive creation, full control mapping, operator routes,
UI views, and release-readiness gates remain later-phase work.

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

If those exports are missing, current Phase 2 evidence commands fail clearly
and tell the user to generate V12 governance exports first.

## Claim Boundary

This evidence pack supports review and audit preparation.
It does not certify compliance with any legal, regulatory, security, or
organizational framework.

Future pack outputs must not imply certification, auditor approval, framework
conformance, control effectiveness, or legal readiness. JSON artifacts are the
planned canonical contract; Markdown is presentation only.

## Safety Boundary

Pack references are planned to be project-relative, normalized, allowlisted,
hash-indexed, schema-versioned where applicable, and tagged with redaction
status. Raw provider payloads, credentials, API keys, environment values, raw
headers, private uploads, PII, customer data, secret values, absolute machine
paths, raw vector database internals, and arbitrary workspace files must not
enter pack outputs.
