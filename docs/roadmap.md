# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using V2 config, task, policy, and template inputs; a deterministic mock agent;
configured provider profiles; provider-input policy gates; local lexical and
local dense fixture retrieval evidence; approval-bound template application;
separate `git_commit` approval; packaged benchmark adapters; provider audit
demos; release-readiness reports; audit logs; evals; an optional LangGraph
boundary proof; and reproducible artifacts.

## V3 / Future Priorities

- Live provider smoke implementation beyond recorded fixtures.
- Richer scanner gates and optional external report ingestion.
- Template catalog expansion beyond the bundled Python trio.
- Benchmark adapters beyond bundled local samples.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add an MCP adapter behind a capability flag.
- Add external template catalogs and remote template discovery.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
- Add production Qdrant server mode and deployment-scale retrieval tuning.
- Add enterprise/compliance readiness work, including production identity,
  centralized secrets management, hardened sandboxing, and attestation.
