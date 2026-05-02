# Local Operator Surface

## Status

The local operator surface is the implemented v1.3.0 track for the v1.3.0 release
target. It is described by [the v1.3.0 PRD](prd-agent-harness-v1.3.0-local-operator-surface.md) and
[the v1.3.0 plan](../plans/agent-harness-v1.3.0-local-operator-surface.md).

This page records the implemented local boundary. It must not describe later
hosted, enterprise, MCP, or multi-agent behavior as current until tests and
release evidence exist.

## Implemented in v1.3.0

Phases 1 through 8 have added the safe `agent-harness serve` shell and the
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
  actor and reason text, and posts approve/deny decisions to the existing v1.3.0
  approval decision API
- UI approval errors are shown from the API response, including already-decided,
  binding, and drift failures, while the approval artifact remains the source of
  truth
- release readiness reports operator evidence for app import, API smoke, token
  enforcement, host rejection, approval binding, and packaged static UI assets
- CI installs the operator extra for Python checks and runs focused operator
  release gates before the release-readiness report

## Implemented v1.9.0 Evidence API Extension

The local operator API also exposes token-protected read-only evidence pack
inspection routes:

- `GET /api/v1/evidence/overview`
- `GET /api/v1/evidence/packs`
- `GET /api/v1/evidence/packs/{pack_id}`
- `GET /api/v1/evidence/control-map`
- `GET /api/v1/evidence/artifact-index`
- `GET /api/v1/evidence/findings`

These routes read existing evidence pack artifacts under the configured
`.agent-harness` evidence root. They do not generate packs, mutate evidence,
serve arbitrary files, or expose raw provider payloads, secrets, or absolute
paths.

## Implemented v1.9.0 Evidence UI Extension

The packaged local operator UI includes a read-only Evidence Pack section. It
uses the existing in-memory operator token, calls only local
`/api/v1/evidence/*` routes, and renders:

- Overview
- Control Mapping
- Artifact Index
- Findings
- Exported Packs
- Release Evidence

The Evidence Pack section shows missing pack and blocking finding states from
the API. It does not generate packs, mutate evidence, use external assets,
call remote services, add analytics, or persist evidence state in browser
storage.

The operator surface is not a new runtime. The CLI and existing runtime remain
responsible for task execution, provider setup, template application, patch
planning, and git commit planning.

## Roadmap / Not implemented yet

These remain outside the completed v1.3.0 local operator implementation:

- release tagging and package publishing for v1.3.0

These remain outside the v1.3.0 local operator scope:

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
- evidence pack generation from the API or UI

## Safety Boundaries

The planned v1.3.0 security model is intentionally local and modest:

- bind only to `127.0.0.1`, `localhost`, or `::1`
- require `X-Agent-Harness-Operator-Token` for `/api/v1/*`
- keep generated tokens in memory by default
- avoid wildcard CORS
- expose only allowlisted run artifact classes
- deny raw provider payloads, credentials, environment values, ignored caches,
  arbitrary workspace files, and files outside known artifact roots
- route all approval decisions through the existing approval service

v1.3.0 must not present the in-memory token as enterprise authentication or the
local server as a hosted platform.

## Golden Path

From a clean checkout with the operator extra installed:

```powershell
uv sync --extra operator
uv run agent-harness demo provider-audit
uv run agent-harness serve --host 127.0.0.1 --port 8765
```

The serve command prints a generated in-memory operator token when `--token` is
omitted. Open the local URL, enter that token in the UI, inspect the
provider-audit run, and use the approvals panel only for existing pending
approvals.

## Release Evidence

`agent-harness release readiness` reports the operator gate under:

- `operator.app_factory`
- `operator.api_smoke`
- `operator.token_required`
- `operator.host_rejection`
- `operator.approval_binding`
- `operator.static_ui`

The CI release-evidence job installs `agent-harness[operator]` and runs focused
operator CLI, API, UI, and release-readiness tests before recording the final
readiness report.
