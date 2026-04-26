# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow using a
deterministic mock agent, policy-gated tools, explicit context manifests,
approval binding, audit logs, evals, and reproducible artifacts.

## Next Priorities

- Add `git_commit` for exact approved files only.
- Add an OpenAI-compatible provider adapter behind explicit network approval.
- Expand the template catalog.
- Strengthen Qdrant/server retrieval modes.
- Add richer benchmark adapters.
- Tighten scanner gates beyond critical findings.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add an MCP adapter behind a capability flag.
- Add an optional LangGraph adapter package.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
