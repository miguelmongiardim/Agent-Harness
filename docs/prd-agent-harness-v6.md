# PRD: Agent Harness V6 Local Operator Surface

## Problem Statement

Agent Harness v1.2.0 proves a local-first control plane for policy-gated
software-engineering agent workflows: deterministic runs, provider evidence,
approval binding, retrieval scorecards, context manifests, exports, and release
readiness. The remaining operator workflow is still mostly terminal-bound.

A reviewer can inspect artifacts through CLI commands, but the original product
conception calls for a human-readable operator surface for approvals and run
inspection. Without V6, review of a paused run requires knowing the artifact
layout and CLI inspection commands. That makes approval review harder to
demonstrate and increases the chance that reviewers treat the stored evidence as
opaque files instead of an auditable control plane.

The affected users are local developers, reviewers, maintainers, and security
reviewers who need to inspect a run, evaluate pending approvals, and verify that
decisions are recorded through the same policy and audit behavior as the CLI.

## Solution

V6 introduces a local-only operator surface for v1.3.0: an optional web API and
packaged static UI over existing Agent Harness run artifacts and approval
services. The server exposes the current control plane. It does not replace the
CLI or runtime.

The primary reviewer workflow is:

1. Install the optional operator extra.
2. Run an existing demo or task through the CLI.
3. Start `agent-harness serve` on a loopback host.
4. Open the local UI and provide the operator token.
5. Inspect run list, run details, events, context, artifacts, provider evidence,
   security findings, retrieval scorecards, and pending approvals.
6. Approve or deny an existing pending approval through the UI.
7. Verify that CLI inspection shows the same approval state and audit evidence.

V6 deliberately avoids hosted service behavior, non-loopback binding, remote web
UI operation, multi-user authentication, run creation, config editing, template
application, direct patch application, direct git commit creation, direct
provider execution, MCP, multi-agent orchestration, enterprise readiness, and
compliance readiness.

## Implemented in V6

The V6 target scope is a local operator surface:

- optional `agent-harness[operator]` dependencies for FastAPI and uvicorn
- `agent-harness serve` with loopback-only host validation
- in-memory operator token support for local API access
- token-protected `/api/v1/*` routes
- health, run list, run detail, context, approvals, approval decision, and
  policy inspection routes
- versioned operator response contracts
- artifact allowlisting for known run evidence
- approval decisions routed through the existing approval service
- packaged static UI with no Node build and no external runtime assets
- release-readiness evidence for operator API, UI packaging, token checks, and
  loopback-only behavior

## Roadmap / Not implemented yet

The following are not part of V6:

- hosted API
- remote web UI
- multi-user authentication
- enterprise control plane
- cloud deployment
- production web service claims
- compliance readiness
- MCP resources, prompts, or tool execution
- multi-agent orchestration
- run creation from the UI or API
- config, task, template, or policy editing from the UI or API
- direct patch, commit, or provider execution from the UI or API
- arbitrary filesystem browsing

## User Stories

1. As a local reviewer, I want to start a local operator UI, so that I can
   inspect Agent Harness run evidence without memorizing artifact paths.
2. As a local reviewer, I want to inspect a run list and run details, so that I
   can find the run I need to review.
3. As a security reviewer, I want to inspect context manifests, policy evidence,
   security findings, provider evidence, and retrieval scorecards, so that I can
   verify what evidence influenced the run.
4. As an approver, I want to review pending approvals in a browser, so that I
   can make an explicit approve or deny decision with actor and reason evidence.
5. As a maintainer, I want UI approval decisions to route through the existing
   approval service, so that drift checks, checkpoint checks, and approval
   bindings remain unchanged.
6. As a CLI user, I want CLI inspection and UI inspection to show the same
   approval state, so that the operator surface does not create a parallel
   source of truth.
7. As a security-minded maintainer, I want the operator server to bind only to
   loopback hosts, so that V6 does not introduce network exposure by default.
8. As a security-minded maintainer, I want `/api/v1/*` routes to require an
   operator token, so that accidental local access is gated without claiming
   enterprise authentication.
9. As a package user, I want the base install to remain CLI-first, so that
   FastAPI and uvicorn are not required unless I opt into the operator surface.
10. As a release reviewer, I want release readiness to verify the operator API,
    token requirement, loopback binding, static UI packaging, and claim
    boundaries, so that V6 can be accepted from a clean checkout.

## Behavioral Requirements

1. Base installs do not require FastAPI or uvicorn.
2. `agent-harness[operator]` installs the dependencies needed to run the local
   operator server.
3. `agent-harness serve` exists and defaults to `--host 127.0.0.1 --port 8765`
   and `--profile default`.
4. `agent-harness serve` fails clearly with an install hint for
   `agent-harness[operator]` when operator dependencies are missing.
5. `agent-harness serve` accepts only `127.0.0.1`, `localhost`, and `::1` as
   host values.
6. `agent-harness serve` rejects `0.0.0.0`, public IPs, private LAN IPs, and
   hostnames that do not resolve to loopback.
7. If `--token` is omitted, the serve command generates an in-memory token and
   prints it once to the terminal.
8. Generated tokens are not persisted, not written to run artifacts, and not
   logged by the application.
9. `/health` returns `operator_health.v1` and can work without run storage.
10. Every `/api/v1/*` route requires `X-Agent-Harness-Operator-Token`.
11. Missing or invalid API tokens return an authorization error without leaking
    the configured token.
12. `GET /api/v1/runs` returns a versioned run list from existing run storage.
13. `GET /api/v1/runs/{run_id}` returns versioned run detail using existing
    summary, event, artifact, provider, security, template, git, and retrieval
    evidence when those artifacts exist.
14. `GET /api/v1/runs/{run_id}/context` returns the existing context manifest
    evidence for that run.
15. `GET /api/v1/runs/{run_id}/approvals` returns pending and decided approval
    records for that run.
16. `GET /api/v1/policy/{profile}` returns policy inspection evidence without
    secrets or unsafe local filesystem details.
17. API responses distinguish missing artifacts, denied artifacts, and malformed
    artifacts with safe error messages.
18. The operator API reads artifacts only through existing storage, policy, and
    approval abstractions.
19. The operator API cannot expose arbitrary filesystem paths or arbitrary
    workspace file contents.
20. Allowed read-only artifact classes are run summaries, events, tool calls,
    context manifests, approval records, policy decisions, redacted provider
    evidence, security findings, eval results, retrieval scorecards, and
    exported Markdown/JSON/SARIF artifacts.
21. Raw provider payloads, credentials, environment variables, ignored local
    caches, arbitrary workspace files, and files outside known artifact roots
    are denied by default.
22. `POST /api/v1/runs/{run_id}/approvals/{action_id}/decision` accepts only
    `approve` or `deny`, with optional `actor` and `reason`.
23. Approval decisions call the existing approval service used by the CLI.
24. The approval decision endpoint cannot bypass approval binding, drift,
    checkpoint, or policy checks.
25. Already-decided approvals return conflict.
26. Missing runs and missing approval actions return not found.
27. Approval decisions are written to the same approval artifacts and event log
    shape as CLI decisions.
28. CLI inspect and UI/API inspect show the same approval state after a decision.
29. The static UI is packaged with the Python distribution.
30. The static UI has no Node build, external CDN dependencies, remote fonts,
    analytics, or external API calls.
31. The static UI uses only `/api/v1/...` local API routes.
32. The static UI displays local-only and non-hosted status.
33. The UI lets a reviewer list runs, open a run, inspect timeline, context,
    artifacts, provider evidence, security or policy findings, eval or
    scorecard evidence, and pending approvals.
34. The UI lets a reviewer approve or deny pending approvals through the V6 API.
35. Release readiness reports operator evidence, including API smoke, static UI
    packaging, no external UI references, loopback host rejection, token
    enforcement, approval binding enforcement, and docs claim boundaries.
36. Docs distinguish local operator API/UI behavior from hosted API, remote UI,
    enterprise control plane, MCP, multi-agent, cloud, production web service,
    and compliance claims.

## Implementation Decisions

- Preserve the existing CLI and runtime as the source of run creation and
  execution behavior.
- Add `agent-harness serve` as the only new public CLI command for V6.
- Add `agent_harness.operator` as the operator boundary. It should expose an
  app factory and reuse existing storage, policy, artifact, and approval
  services.
- Use FastAPI and uvicorn only behind the optional `operator` extra because the
  local HTTP API is the user-facing capability being added.
- Keep the base install free of operator dependencies.
- Add `httpx` to dev/test dependencies so operator API tests can exercise the
  app through public HTTP behavior.
- Add versioned response contracts: `operator_health.v1`,
  `operator_run_list.v1`, `operator_run_detail.v1`, and
  `operator_approval_decision.v1`.
- Reuse existing public artifact shapes such as `summary.v1`, `approval.v1`,
  `context_manifest.v2`, provider evidence, security findings, template
  evidence, git evidence, export evidence, and retrieval scorecards.
- Keep `/health` as the only route that may be callable without the operator
  token.
- Require `X-Agent-Harness-Operator-Token` for all `/api/v1/*` routes.
- Keep tokens in memory only unless a future PRD defines a stronger
  authentication model.
- Do not enable wildcard CORS. The default UI is same-origin.
- Do not introduce arbitrary file-serving or artifact path parameters.
- Serve static UI assets from packaged files and keep them offline-capable.
- Extend release readiness instead of adding a separate operator evidence
  command.

## Testing Decisions

- Start each implementation slice with one failing public-interface test and
  implement only the minimum behavior needed to turn it green.
- Test the serve command through CLI behavior, including missing optional
  dependency diagnostics and loopback host validation.
- Test the operator app through HTTP client behavior, not private route helpers.
- Test approval decisions through the same artifacts and CLI inspect evidence
  used by the existing approval flow.
- Add adversarial or regression tests proving the API cannot bypass approval
  binding, approve already-decided actions, approve tampered actions, approve
  missing actions, expose raw provider payloads, expose environment values, or
  read arbitrary files.
- Add UI packaging tests that parse static assets and reject external CDN,
  remote font, analytics, and external API references.
- Add docs-check coverage that allows local operator API/UI claims only in V6
  implemented sections and still blocks hosted, enterprise, MCP, multi-agent,
  cloud, production web service, and compliance claims outside roadmap sections.
- Keep tests focused on public CLI, API, artifact, and release-readiness
  behavior.

## Out of Scope

- Hosted API.
- Remote web UI.
- Multi-user authentication.
- Enterprise identity or enterprise control plane.
- Compliance readiness.
- Cloud deployment.
- Production web service operation.
- MCP.
- Multi-agent orchestration.
- Starting runs from the UI or API.
- Editing config, policy, tasks, templates, or provider profiles from the UI or
  API.
- Applying templates from the UI or API.
- Direct patch application from the UI or API.
- Direct git commit creation from the UI or API.
- Direct provider execution from the UI or API.
- Arbitrary filesystem browsing.
- External frontend build system.

## Further Notes

- The security model is intentionally modest: loopback binding plus an
  in-memory token for local operation. V6 must not describe this as enterprise
  authentication.
- The highest-risk behavior is approval mutation. It must stay inside the
  existing approval service and preserve all existing approval binding and drift
  checks.
- The second highest-risk behavior is artifact exposure. V6 should add an
  explicit allowlist instead of exposing user-supplied file paths.
- The golden path is:

  ```powershell
  uv sync --extra operator
  uv run agent-harness demo provider-audit
  uv run agent-harness serve --host 127.0.0.1 --port 8765
  ```

