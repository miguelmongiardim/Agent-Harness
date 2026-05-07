# agent_harness.governance

## Purpose

`agent_harness.governance` owns local governance summaries, checks, reports, and
exports over the current workspace artifacts. It aggregates policy, run,
approval, provider, retrieval, template, skill, MCP, multi-agent, security, and
release-readiness signals into inspectable governance evidence.

The package reports local evidence posture. It does not certify compliance,
perform external audits, or replace the policy engine that made the original
decisions.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Governance domains, diagnostics, findings, summaries, reports, exports, and status schemas. |
| `summary.py` | Builds workspace-level governance summaries from config, policy, run indexes, and optional domain summaries. |
| `checks.py` | Runs blocking/non-blocking governance checks over docs, raw payload risks, unsafe artifact references, and required evidence. |
| `reports.py` | Builds governance reports, renders Markdown, and writes export artifacts. |
| `__init__.py` | Exports summary, check, report, render, and export functions. |

## Governance Flow

`build_governance_summary()` inspects the configured artifact root and records
domain status, findings, and diagnostics. `run_governance_check()` turns
workspace issues into a check result that can block release or evidence pack
creation. `export_governance()` writes stable artifacts consumed by release
readiness, the local operator surface, and evidence pack generation.

## Boundaries

Governance reads evidence; it should not regenerate runs, approve actions,
perform provider calls, or mutate policy. When it finds missing or malformed
data, it should report diagnostics with artifact references that are safe to
share.
