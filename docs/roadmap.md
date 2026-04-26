# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using V2 config, task, policy, and template inputs; a deterministic mock agent;
configured provider profiles; provider-input policy gates; local lexical and
local dense fixture retrieval evidence; approval-bound template application;
separate `git_commit` approval; packaged benchmark adapters; provider audit
demos; release-readiness reports; audit logs; evals; an optional LangGraph
boundary proof; and reproducible artifacts.

## V3 Direction

V3 is planned as operational integration hardening. The scope is based on the
remaining gaps between V2 and the original deep-research direction: real
provider smoke evidence, executable scanner and SBOM adapters, retention and
logging profiles, trace correlation, local Qdrant server mode, a `docs-rag`
template, and a read-only MCP adapter boundary.

The detailed V3 plan lives in [plans/agent-harness-v3.md](../plans/agent-harness-v3.md).

## V3 Priorities

- Live provider smoke evidence beyond recorded fixtures.
- Policy-mediated Gitleaks, Semgrep, Trivy, and CycloneDX adapter evidence.
- Configurable audit retention and redacted/non-redacted logging modes.
- Trace correlation and operational metrics across runs, approvals, tools,
  retrieval, providers, exports, and benchmarks.
- Local Qdrant server mode without remote embeddings.
- Template catalog expansion starting with `docs-rag`.
- Read-only MCP resources and prompts behind an explicit capability flag.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add external template catalogs and remote template discovery.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
- Add production Qdrant server mode and deployment-scale retrieval tuning.
- Add enterprise/compliance readiness work, including production identity,
  centralized secrets management, hardened sandboxing, and attestation.
