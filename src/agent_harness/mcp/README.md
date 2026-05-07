# agent_harness.mcp

## Purpose

`agent_harness.mcp` owns the local read-only Model Context Protocol boundary for
Agent Harness evidence. It exposes runs, policies, templates, skills,
orchestrations, prompts, and selected evidence artifacts through stable
resource and prompt registries.

MCP support is an interoperability layer over existing local evidence. It is not
a runtime, not a tool-execution surface, and not a write-capable remote server.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | MCP resource, prompt, envelope, content, and access-log schemas. |
| `resources.py` | Lists and reads `agent-harness://` resources with URI validation, policy filtering, orchestration resource handling, and metadata-only access logging. |
| `prompts.py` | Lists and renders local prompts for inspecting runs, policies, templates, skills, and orchestrations. |
| `access_log.py` | Appends MCP access evidence without recording raw private payloads. |
| `server.py` | Optional stdio MCP SDK integration that delegates to the same resource and prompt registries. |
| `__init__.py` | Lazily exports public resource and prompt functions. |

## Resource Model

Resources are addressed with `agent-harness://` URIs. Collection resources list
available runs, templates, skills, and orchestrations. Detail resources read
specific summaries, manifests, events, children, handoffs, templates, skills,
or policies when the URI is valid and the configured local evidence exists.

## Boundaries

This package must remain read-only. Mutation-oriented orchestration resource
names such as approve, resume, and run are rejected. Write-capable MCP tools,
HTTP transports, hosted gateways, and remote registries belong outside the
current implemented boundary.
