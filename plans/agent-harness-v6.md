# Plan: Agent Harness V6 Local Operator Surface

> Source PRD: [docs/prd-agent-harness-v6.md](../docs/prd-agent-harness-v6.md)

Phases 0, 1, 2, 3, and 4 have been implemented. Remaining acceptance boxes
should be checked only after behavior is backed by tests, docs, or release
evidence.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness serve`; preserve all existing run,
  approval, inspect, export, demo, retrieval, and release commands.
- **Operator dependency boundary**: keep FastAPI and uvicorn behind
  `agent-harness[operator]`; base install remains CLI-first.
- **API boundary**: add `agent_harness.operator` with an app factory over
  existing storage, policy, artifact, and approval services.
- **Route shape**: expose `/health` and token-protected `/api/v1/*` routes for
  runs, run detail, context, approvals, approval decisions, and policy
  inspection.
- **Key models**: add `operator_health.v1`, `operator_run_list.v1`,
  `operator_run_detail.v1`, `operator_context.v1`, `operator_policy.v1`, and
  `operator_approval_decision.v1`; reuse existing artifact schemas where
  available.
- **Storage boundary**: read only known run evidence under the configured
  artifact root; do not expose arbitrary filesystem reads.
- **Approval boundary**: the only mutating API behavior is approve/deny for
  existing pending approvals, routed through the existing approval service.
- **Security boundary**: loopback-only server, token-protected API routes,
  same-origin UI by default, no wildcard CORS, no token persistence by default.
- **UI boundary**: package static HTML/CSS/JS with no Node build, no external
  CDN, no remote fonts, no analytics, and no external API calls.
- **Release boundary**: V6 targets v1.3.0 and stays limited to local operator
  inspection and approval.

---

## Phase 0: V6 Scope Is Documented And Guarded

**User stories covered**

- Story 7: maintainer can verify local-only server scope.
- Story 10: release reviewer can distinguish V6 behavior from roadmap claims.

**Observable behaviors**

- V6 PRD and plan exist.
- Operator docs describe local operator API/UI as the target scope.
- Docs checks fail when hosted, enterprise, MCP, multi-agent, cloud, production
  web service, or compliance claims appear as implemented behavior.

**First RED test**

- `agent-harness docs check` passes while a doc claims hosted operator API or
  enterprise web UI as implemented V6 behavior.

### What to build

Add the V6 PRD, plan, operator docs, README/roadmap positioning, and docs-check
guard updates needed to separate local operator behavior from roadmap claims.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v6.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v6.md` is a vertical-slice implementation plan.
- [x] `docs/operator-ui.md` describes local-only operator scope.
- [x] README and roadmap distinguish local operator API/UI from hosted or
      enterprise UI.
- [x] Docs-check guarded phrases allow implemented local operator wording only
      where appropriate.
- [x] Docs-check guarded phrases keep hosted API, remote web UI, multi-user
      auth, enterprise control plane, MCP, multi-agent, cloud deployment,
      production web service, and compliance claims roadmap-only.
- [x] Docs check passes.

### Out of scope

- Serve command implementation.
- Operator dependencies.
- API routes.
- Static UI.

---

## Phase 1: Serve Command Fails Safely Until Operator Extra Is Installed

**User stories covered**

- Story 7: server is loopback-only.
- Story 8: API access is token-gated.
- Story 9: base install remains CLI-first.

**Observable behaviors**

- `agent-harness serve` exists.
- In a base install without operator dependencies, the command fails with an
  actionable `agent-harness[operator]` install hint.
- Host validation rejects non-loopback hosts before server startup.
- If no token is provided, a generated in-memory token is printed once and is
  not written to run artifacts.

**First RED test**

- `agent-harness serve --host 0.0.0.0` is accepted or fails only after trying to
  start a server.

### What to build

Add the CLI surface, optional dependency diagnostics, loopback host validation,
token generation behavior, and enough command wiring to prove the base-install
and invalid-host paths are safe.

### Acceptance criteria

- [x] `agent-harness serve` is present in CLI help.
- [x] Default host is `127.0.0.1`.
- [x] Default port is `8765`.
- [x] Default profile is `default`.
- [x] Missing FastAPI/uvicorn dependencies fail clearly with an
      `agent-harness[operator]` install hint.
- [x] `127.0.0.1`, `localhost`, and `::1` are accepted host values.
- [x] `0.0.0.0`, public IPs, private LAN IPs, and non-loopback hostnames are
      rejected.
- [x] Generated token is printed once when `--token` is omitted.
- [x] Generated token is not persisted or written to `.agent-harness` artifacts.

### Out of scope

- Real API route implementation beyond startup wiring.
- Static UI.
- Release readiness operator evidence.

---

## Phase 2: Health API Proves The Local Operator App Skeleton

**User stories covered**

- Story 1: local reviewer can start the operator surface.
- Story 10: release reviewer can smoke-test the operator app.

**Observable behaviors**

- With operator extras installed, the app factory imports.
- `/health` returns `operator_health.v1`.
- Health does not require run storage.
- `/api/v1/*` routes reject missing or invalid tokens even before run routes
  are implemented.

**First RED test**

- An HTTP client cannot call an app factory and receive `operator_health.v1`
  without needing an existing `.agent-harness/runs` directory.

### What to build

Create the `agent_harness.operator` app factory, the health response contract,
token middleware/dependency for API routes, and a serve path that starts the app
when optional dependencies are installed.

### Acceptance criteria

- [x] Operator app factory imports when `agent-harness[operator]` dependencies
      are installed.
- [x] `GET /health` returns `operator_health.v1`.
- [x] Health response includes status, Agent Harness version, and local-only
      operator mode metadata.
- [x] Health route does not require run storage.
- [x] Missing token on `/api/v1/*` returns authorization error.
- [x] Invalid token on `/api/v1/*` returns authorization error.
- [x] Authorization errors do not leak configured token values.

### Out of scope

- Run list/detail data.
- Approval decisions.
- Static UI.

---

## Phase 3: Reviewer Can List Runs And Open Run Detail Through The API

**User stories covered**

- Story 2: reviewer can find and inspect a run.
- Story 6: CLI and API read the same run evidence.

**Observable behaviors**

- Token-authenticated API lists existing runs from configured storage.
- Run detail returns summary, events, artifact index, and known optional
  evidence when present.
- Missing runs and malformed artifacts return safe errors.

**First RED test**

- A fixture run that `agent-harness inspect run` can read is not visible through
  `GET /api/v1/runs/{run_id}` with a valid token.

### What to build

Wire the API to existing `RunStore` and config loading. Add versioned run list
and detail responses that reuse existing public artifact shapes and report safe
artifact status for missing or malformed evidence.

### Acceptance criteria

- [x] `GET /api/v1/runs` requires a valid token.
- [x] Run list reads existing run storage.
- [x] Run list returns `operator_run_list.v1`.
- [x] `GET /api/v1/runs/{run_id}` requires a valid token.
- [x] Run detail returns `operator_run_detail.v1`.
- [x] Run detail includes summary, events, and artifact index.
- [x] Run detail includes known optional provider, security, template, git,
      runtime adapter, schema version, and workspace metadata evidence when
      present.
- [x] Missing run returns not found.
- [x] Malformed artifact returns a clear safe error.
- [x] API detail and CLI inspect agree on approval state and run status.

### Out of scope

- Context-specific route.
- Approval mutation.
- Static UI.

---

## Phase 4: Reviewer Can Inspect Context, Policy, And Allowlisted Artifacts

**User stories covered**

- Story 3: security reviewer can inspect context, policy, provider, security,
  eval, and scorecard evidence.
- Story 8: API remains token-protected.

**Observable behaviors**

- Context route returns existing context manifest evidence.
- Policy route returns policy inspection evidence without secrets.
- Artifact exposure is allowlisted and does not accept arbitrary file paths.
- Raw provider payloads, env values, credentials, ignored caches, and arbitrary
  workspace files are not exposed.

**First RED test**

- An API caller can request or infer an arbitrary local file path through run
  artifact access.

### What to build

Add context and policy routes plus a safe artifact summary boundary for known
evidence classes. Keep artifact access typed and run-scoped.

### Acceptance criteria

- [x] `GET /api/v1/runs/{run_id}/context` requires a valid token.
- [x] Context route returns existing `context_manifest.v2` evidence.
- [x] Missing context manifest returns a missing-artifact status.
- [x] Malformed context manifest returns a safe malformed-artifact status.
- [x] `GET /api/v1/policy/{profile}` requires a valid token.
- [x] Policy route returns a redaction-safe policy summary.
- [x] API distinguishes missing artifact, denied artifact, and malformed
      artifact.
- [x] API exposes only allowlisted artifact classes.
- [x] API does not expose arbitrary workspace files or absolute local paths.
- [x] API does not expose raw provider payloads, env values, credentials, or
      ignored caches.

### Out of scope

- Approval mutation.
- Static UI rendering.
- New artifact schemas unrelated to operator responses.

---

## Phase 5: Approval Decisions Use The Existing Approval Service

**User stories covered**

- Story 4: approver can make approve/deny decisions.
- Story 5: decisions preserve approval binding and drift checks.
- Story 6: CLI and UI/API show the same approval state.

**Observable behaviors**

- API lists pending and decided approvals.
- API approves or denies an existing pending approval through existing
  `approve_action` behavior.
- Tampered, drifted, missing, or already-decided approvals cannot be approved.
- Decision artifacts and events match CLI approval behavior.

**First RED test**

- A tampered pending approval can be approved through the API even though CLI
  approval would reject it.

### What to build

Add approval list and decision routes. Route all mutation through the existing
approval service and map domain errors to clear HTTP responses.

### Acceptance criteria

- [ ] `GET /api/v1/runs/{run_id}/approvals` requires a valid token.
- [ ] Approval list returns pending and decided approvals.
- [ ] Decision endpoint accepts only `approve` or `deny`.
- [ ] Decision endpoint accepts optional `actor` and `reason`.
- [ ] Decision endpoint calls the existing approval service.
- [ ] Approval binding checks cannot be bypassed.
- [ ] Drift and checkpoint checks cannot be bypassed.
- [ ] Already-decided approvals return conflict.
- [ ] Missing run returns not found.
- [ ] Missing action returns not found.
- [ ] Failed binding checks surface clear safe errors.
- [ ] Decision writes the same approval artifact shape as CLI approval.
- [ ] Decision appends auditable run events.
- [ ] CLI inspect shows the same state after API approval or denial.

### Out of scope

- Creating runs.
- Applying patches directly.
- Creating commits directly.
- Editing tasks, policy, config, or templates.
- Triggering provider calls directly.

---

## Phase 6: Static UI Can Inspect Runs Without External Assets

**User stories covered**

- Story 1: reviewer can open a local operator UI.
- Story 2: reviewer can inspect run list and run detail.
- Story 3: reviewer can inspect context and evidence tabs.

**Observable behaviors**

- `/` serves packaged static UI.
- Static assets load from the package.
- UI uses only local `/api/v1/...` routes.
- UI displays local-only and non-hosted status.
- UI can list runs, open run detail, and display timeline, context, provider,
  security, eval, scorecard, and artifact evidence.

**First RED test**

- The packaged UI references an external CDN, remote font, analytics endpoint,
  or non-local API URL.

### What to build

Add packaged static HTML/CSS/JS that consumes existing V6 API routes. Keep the
UI simple, offline-capable, and operationally dense.

### Acceptance criteria

- [ ] `GET /` serves the static UI.
- [ ] Static assets load from packaged files.
- [ ] Packaged files are included in the Python distribution.
- [ ] UI has no Node build.
- [ ] UI has no external CDN references.
- [ ] UI has no remote font references.
- [ ] UI has no analytics references.
- [ ] UI has no external API calls.
- [ ] UI references only `/api/v1/...` local API paths.
- [ ] UI displays local-only/non-hosted status.
- [ ] UI can list runs with a valid token.
- [ ] UI can open run details with a valid token.
- [ ] UI can display timeline, context, provider evidence, security/policy
      findings, eval/scorecard evidence, and artifacts.

### Out of scope

- Frontend framework setup.
- Hosted UI behavior.
- Multi-user auth.
- Websocket or live-update behavior.

---

## Phase 7: Static UI Can Approve Or Deny Pending Approvals

**User stories covered**

- Story 4: approver can decide pending approvals in the browser.
- Story 5: UI cannot bypass existing approval service.
- Story 6: CLI and UI/API remain consistent.

**Observable behaviors**

- UI approval panel displays pending and decided approvals.
- UI approve/deny controls call the V6 decision API.
- UI reflects decision results and error states.
- CLI inspect sees the same decision state.

**First RED test**

- A pending approval can be decided through the UI without calling the V6
  approval decision route or without updating existing approval artifacts.

### What to build

Wire the UI approvals panel to the approval list and decision APIs. Ensure the
UI presents binding/drift errors clearly without hiding the underlying audit
state.

### Acceptance criteria

- [ ] UI displays pending approvals.
- [ ] UI displays decided approvals.
- [ ] UI approve control calls the decision API with `decision: approve`.
- [ ] UI deny control calls the decision API with `decision: deny`.
- [ ] UI can send optional actor and reason.
- [ ] UI shows already-decided conflict responses.
- [ ] UI shows failed binding/drift errors.
- [ ] UI refreshes approval state after a decision.
- [ ] CLI inspect sees the same approval state after UI decision.
- [ ] Decision remains auditable in existing artifacts and events.

### Out of scope

- Creating new approvals.
- Batch approval.
- Editing approval bindings.
- Direct mutation outside existing approval service.

---

## Phase 8: Operator Golden Path Is Release-Ready

**User stories covered**

- Story 1: reviewer can start the UI.
- Story 4: reviewer can approve or deny through UI.
- Story 10: release reviewer can accept V6 from clean checkout evidence.

**Observable behaviors**

- The documented V6 golden path works with operator extras installed.
- Release readiness reports operator evidence.
- CI validates API token requirements, host rejection, approval binding, static
  UI packaging, and docs claim boundaries.

**First RED test**

- `agent-harness release readiness` reports ready for v1.3.0 even when the
  operator app factory cannot import or the static UI is missing from package
  data.

### What to build

Add release-readiness operator evidence, CI coverage, final docs updates, and
the golden-path documentation. Keep V6 scoped to local operator behavior.

### Acceptance criteria

- [ ] V6 golden path works:

      ```powershell
      uv sync --extra operator
      uv run agent-harness demo provider-audit
      uv run agent-harness serve --host 127.0.0.1 --port 8765
      ```

- [ ] Reviewer can open the local UI.
- [ ] Reviewer can inspect run list.
- [ ] Reviewer can inspect run details.
- [ ] Reviewer can inspect timeline.
- [ ] Reviewer can inspect context manifest.
- [ ] Reviewer can inspect provider evidence.
- [ ] Reviewer can inspect security and policy findings.
- [ ] Reviewer can inspect eval and retrieval scorecard evidence.
- [ ] Reviewer can review pending approvals.
- [ ] Reviewer can approve or deny through the UI.
- [ ] Approval decision is reflected in run artifacts.
- [ ] CLI inspect shows the same approval state.
- [ ] API is token-protected.
- [ ] Server rejects non-loopback bind.
- [ ] UI has no external CDN or remote dependencies.
- [ ] Release readiness verifies operator evidence.
- [ ] CI validates packaged static UI.
- [ ] CI validates token requirements.
- [ ] CI validates host rejection.
- [ ] CI validates approval binding cannot be bypassed.
- [ ] Docs do not claim hosted, enterprise, MCP, multi-agent, cloud,
      production web service, or compliance capabilities.
- [ ] Docs check passes.

### Out of scope

- Tagging v1.3.0.
- Publishing packages.
- Hosted deployment.
- Enterprise authentication.
- MCP or multi-agent behavior.

## Cross-Phase Invariants

- V6 exposes the existing control plane; it does not create a parallel runtime.
- Base install remains CLI-first.
- Operator dependencies remain optional.
- Server binding remains loopback-only.
- `/api/v1/*` routes require a token.
- Tokens are not persisted by default and are not written to run artifacts.
- No API route exposes arbitrary filesystem reads.
- Raw provider payloads, credentials, env var values, ignored caches, and
  arbitrary workspace files remain denied.
- The only mutating API behavior is approve/deny for existing pending
  approvals.
- Approval decisions route through the existing approval service.
- Approval binding, drift, checkpoint, and policy checks are not bypassed.
- All approval decisions remain auditable through existing artifacts and events.
- Static UI assets are packaged, offline-capable, and free of external runtime
  dependencies.
- Tests verify public CLI, API, artifact, approval, UI, and release behavior.
- No subsystem is added unless the current or next slice exercises it through an
  observable behavior.
- Docs keep local operator behavior separate from hosted, enterprise, MCP,
  multi-agent, cloud, production web service, and compliance roadmap claims.

## TDD Execution Rules

- Choose one observable behavior per slice.
- Write one failing public-interface test first.
- Implement the minimum code needed for green.
- Refactor only after tests are green.
- Do not build horizontal infrastructure unless the current or immediately next
  slice exercises it.
- Do not write all tests upfront.
- Do not implement roadmap features without an observable behavior and an
  acceptance test.

## Final Acceptance

V6 is complete only when the following path works from a clean checkout with
operator extras installed:

```powershell
uv sync --extra operator

uv run agent-harness demo provider-audit

uv run agent-harness serve --host 127.0.0.1 --port 8765
```

V6 is also complete only when a reviewer can open the local UI, inspect run
list and run details, inspect timeline/context/provider/security/policy/eval
and retrieval scorecard evidence, review pending approvals, approve or deny
through the UI, verify the approval decision in run artifacts, verify CLI
inspect shows the same approval state, and confirm release readiness reports
operator evidence without hosted, enterprise, MCP, multi-agent, cloud,
production web service, or compliance claims.
