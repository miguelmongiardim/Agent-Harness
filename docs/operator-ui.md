# Local Operator Surface

## Status

The local operator surface is the planned V6 track for v1.3.0. It is described
by [the V6 PRD](prd-agent-harness-v6.md) and
[the V6 plan](../plans/agent-harness-v6.md).

This page records the intended boundary as V6 is implemented. It must be
updated as each V6 phase lands, and it must not describe later behavior as
current until tests and release evidence exist.

## Implemented in V6

Phases 1 through 7 have added the safe `agent-harness serve` shell and the
first local operator run-inspection APIs:

- the `operator` optional dependency extra is declared
- `serve` defaults to `127.0.0.1:8765` and profile `default`
- `serve` accepts only `127.0.0.1`, `localhost`, and `::1`
- `serve` rejects wildcard, public, private LAN, and unknown hostnames before
  startup
- missing FastAPI or uvicorn dependencies report an
  `agent-harness[operator]` install hint
- when no token is provided, `serve` prints one generated in-memory token and
  does not persist it to run artifacts
- with operator dependencies installed, `serve` builds the local operator app
  and starts it through uvicorn
- `agent_harness.operator` exposes an app factory for the local API
- `GET /health` returns `operator_health.v1` without requiring run storage
- `/api/v1/*` routes require `X-Agent-Harness-Operator-Token`
- missing or invalid operator tokens return authorization errors without
  leaking the configured token
- `GET /api/v1/runs` returns `operator_run_list.v1` from existing run storage
- `GET /api/v1/runs/{run_id}` returns `operator_run_detail.v1` with summary,
  events, artifact index, and known optional run evidence when present
- missing runs and malformed required run artifacts return safe API errors
  without local filesystem paths
- run detail sanitizes artifact maps so unsafe or non-allowlisted references are
  reported as denied artifacts instead of being echoed
- `GET /api/v1/runs/{run_id}/context` returns `operator_context.v1` with the
  existing `context_manifest.v2` artifact when present
- missing and malformed context manifests return explicit artifact status
  values without leaking local filesystem paths
- `GET /api/v1/policy/{profile}` returns `operator_policy.v1` from existing
  policy loading without exposing environment values
- `GET /api/v1/runs/{run_id}/approvals` returns `operator_approval_list.v1`
  with pending and decided approval records from existing run artifacts
- `POST /api/v1/runs/{run_id}/approvals/{action_id}/decision` returns
  `operator_approval_decision.v1` after approving or denying through the
  existing approval service
- approval decisions preserve binding, checkpoint, and drift checks; failed
  checks return safe API errors without marking the approval decided
- API approval decisions write the same approval artifacts and run events that
  CLI approval uses
- `GET /` serves a packaged static operator UI
- packaged HTML, CSS, and JavaScript assets are served locally from the Python
  distribution with no Node build
- the UI stores the operator token only in browser memory for the current page
  session and uses local `/api/v1/...` routes only
- the UI can list runs, open run detail, and show timeline, context, artifacts,
  provider evidence, security/policy evidence, eval/scorecard evidence, and
  approvals
- the UI approval panel displays pending and decided approvals, accepts optional
  actor and reason text, and posts approve/deny decisions to the existing V6
  approval decision API
- UI approval errors are shown from the API response, including already-decided,
  binding, and drift failures, while the approval artifact remains the source of
  truth

The operator surface is not a new runtime. The CLI and existing runtime remain
responsible for task execution, provider setup, template application, patch
planning, and git commit planning.

## Roadmap / Not implemented yet

These remain unimplemented after Phase 7:

- final release-readiness operator evidence and CI gates

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
