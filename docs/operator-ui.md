# Local Operator Surface

## Status

The local operator surface is the planned V6 track for v1.3.0. It is described
by [the V6 PRD](prd-agent-harness-v6.md) and
[the V6 plan](../plans/agent-harness-v6.md).

This page records the intended boundary as V6 is implemented. It must be
updated as each V6 phase lands, and it must not describe later behavior as
current until tests and release evidence exist.

## Implemented in V6

Phase 1 has added the safe `agent-harness serve` CLI shell:

- the `operator` optional dependency extra is declared
- `serve` defaults to `127.0.0.1:8765` and profile `default`
- `serve` accepts only `127.0.0.1`, `localhost`, and `::1`
- `serve` rejects wildcard, public, private LAN, and unknown hostnames before
  startup
- missing FastAPI or uvicorn dependencies report an
  `agent-harness[operator]` install hint
- when no token is provided, `serve` prints one generated in-memory token and
  does not persist it to run artifacts

The operator surface is not a new runtime. The CLI and existing runtime remain
responsible for task execution, provider setup, template application, patch
planning, and git commit planning.

## Roadmap / Not implemented yet

These remain unimplemented after Phase 1:

- operator app factory
- `/health`
- token-protected `/api/v1/*` routes
- run, context, policy, artifact, provider, security, eval, scorecard, and
  approval inspection through the API
- approve or deny through the API or UI
- packaged static UI

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
