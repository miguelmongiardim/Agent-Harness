# MCP Boundary Example

This example is the v1.6.0 golden path for the local read-only MCP boundary.

From a clean checkout:

```powershell
uv sync --extra mcp
uv run agent-harness demo provider-audit
cd examples\provider_audit
uv run agent-harness mcp resources list --json
uv run agent-harness mcp resources read agent-harness://runs/<run-id>/summary --json
uv run agent-harness mcp resources read agent-harness://runs/<run-id>/context --json
uv run agent-harness mcp prompts list --json
uv run agent-harness mcp prompts get agent-harness-run-review --arg run_id=<run-id> --json
uv run agent-harness mcp resources read file:///tmp/secret.txt --json
cd ..\..
uv run agent-harness release readiness
```

Run the optional stdio server from the demo workspace when a client will
connect to it:

```powershell
cd examples\provider_audit
uv run agent-harness mcp serve
```

The expected outputs under `expected/` show the public shapes for resource
listing, prompt listing, and a denied arbitrary file resource. The access log is
written in the demo workspace at `.agent-harness/mcp/access-log.jsonl`.

## Out of Scope

MCP tools, write actions, approval decisions, provider execution, HTTP
transport, hosted service operation, remote gateways, and arbitrary file reads
remain outside this v1.6.0 boundary.
