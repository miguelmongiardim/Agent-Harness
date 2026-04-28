# Local Operator Surface

## Status

The local operator surface is the planned V6 track for v1.3.0. It is described
by [the V6 PRD](prd-agent-harness-v6.md) and
[the V6 plan](../plans/agent-harness-v6.md).

This page records the intended boundary before implementation. It must be
updated as each V6 phase lands, and it must not describe behavior as current
until tests and release evidence exist.

## Implemented in V6

V6 will add a local-only operator API and packaged static UI over existing run
artifacts and approval services. The intended behavior is:

- optional `agent-harness[operator]` dependencies
- `agent-harness serve` bound only to loopback hosts
- in-memory operator token for local API access
- token-protected `/api/v1/*` routes
- run, context, policy, artifact, provider, security, eval, scorecard, and
  approval inspection
- approve or deny for existing pending approvals only
- decisions routed through the same approval service used by the CLI
- packaged static UI with no external runtime assets

The operator surface is not a new runtime. The CLI and existing runtime remain
responsible for task execution, provider setup, template application, patch
planning, and git commit planning.

## Roadmap / Not implemented yet

These remain outside the V6 local operator scope:

- hosted API
- remote web UI
- multi-user authentication
- enterprise control plane
- cloud deployment
- production web service operation
- compliance readiness
- MCP resources, prompts, or tool execution
- multi-agent orchestration
- run creation from the API or UI
- config, task, policy, provider, or template editing from the API or UI
- direct patch, commit, or provider execution from the API or UI
- arbitrary filesystem browsing

## Safety Boundaries

The planned V6 security model is intentionally local and modest:

- bind only to `127.0.0.1`, `localhost`, or `::1`
- require `X-Agent-Harness-Operator-Token` for `/api/v1/*`
- keep generated tokens in memory by default
- avoid wildcard CORS
- expose only allowlisted run artifact classes
- deny raw provider payloads, credentials, environment values, ignored caches,
  arbitrary workspace files, and files outside known artifact roots
- route all approval decisions through the existing approval service

V6 must not present the in-memory token as enterprise authentication or the
local server as a hosted platform.

