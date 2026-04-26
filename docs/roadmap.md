# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using a deterministic mock agent, configured provider profiles, provider-input
policy gates, hybrid context manifests, approval-bound template application,
separate `git_commit` approval, packaged benchmark sample packs, audit logs,
evals, an optional LangGraph boundary proof, and reproducible artifacts.

## Next Priorities

- Tighten scanner gates beyond critical findings.
- Expand the template catalog.
- Add richer benchmark adapters beyond bundled local samples.
- Strengthen Qdrant/server retrieval modes.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add an MCP adapter behind a capability flag.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
