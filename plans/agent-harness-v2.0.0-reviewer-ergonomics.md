# Plan: Agent Harness v2.0.0 Reviewer Ergonomics

> Source PRD:
> [docs/prd-agent-harness-v2.0.0-reviewer-ergonomics.md](../docs/prd-agent-harness-v2.0.0-reviewer-ergonomics.md)

This plan follows the PRD -> Plan -> TDD workflow. Implementation has started
under the separate TDD execution request; acceptance checkboxes below reflect
the current implemented and validated state.

v2.0.0 is an additive reviewer ergonomics release. It introduces one teachable
review entrypoint over existing checks and evidence while preserving existing
CLI, schema, artifact, policy, approval, and release-readiness contracts.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness review profiles`, `status`, `run`,
  and `artifacts`.
- **Profiles**: ship built-in `quick`, `standard`, and `release` profiles.
  Do not add config-driven profile customization in v2.0.0.
- **Key models**: add review profile catalog, review status, review run,
  artifact inventory, artifact inventory item, cleanup plan, and cleanup
  candidate contracts under the review boundary.
- **Schema**: introduce `review_profile_catalog.v1`, `review_status.v1`,
  `review_run.v1`, `artifact_inventory.v1`, and `artifact_cleanup_plan.v1`
  using `StrictModel`.
- **Storage**: write review evidence under `.agent-harness/review/`.
- **Runtime boundary**: review coordinates existing commands and artifacts. It
  does not replace runtime, eval, benchmark, governance, evidence, or release
  readiness behavior.
- **Policy boundary**: review does not widen policy, change profiles, approve
  actions, deny actions, or bypass existing policy-mediated behavior.
- **Approval model**: no new approval mutation exists in v2.0.0 review
  commands.
- **Audit model**: review results record command outcomes, evidence refs, and
  safe next actions with project-relative paths and redacted output summaries.
- **Cleanup boundary**: `review artifacts` is dry-run only. It never deletes
  files in v2.0.0.
- **External service boundary**: no hosted services, new provider calls,
  external benchmark downloads, or remote storage are added.

---

## Phase 0: Scope Docs And Claim Guard

**User stories covered**

- Story 13: documentation reviewer can reject unsupported v2.0.0 claims.

**Observable behaviors**

- v2.0.0 PRD and implementation plan exist as durable planning artifacts.
- Public docs describe v2.0.0 according to the current implementation state.
- Docs checks reject unsupported claims that v2.0.0 adds hosted operation,
  destructive cleanup, live-provider expansion, MCP execution, production
  retrieval, compliance certification, or release-readiness replacement.

**First RED test**

- Add a docs-check integration test that fails when implemented-scope docs
  claim v2.0.0 provides hosted operation, destructive cleanup, MCP tool
  execution, live provider expansion, production retrieval, compliance
  certification, or replacement of release readiness outside roadmap,
  out-of-scope, or denial context.

### What to build

Add the v2.0.0 PRD, vertical plan, roadmap positioning, and docs-check claim
rules. This phase owns docs and claim guards; implementation of the review CLI,
schemas, artifacts, cleanup planning, and release-readiness gates is tracked in
later phases.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v2.0.0-reviewer-ergonomics.md` exists.
- [x] `plans/agent-harness-v2.0.0-reviewer-ergonomics.md` exists.
- [x] README and roadmap identify v2.0.0 reviewer ergonomics scope accurately
      for the current implementation state.
- [x] Docs checks reject unsupported v2.0.0 scope claims.
- [x] Existing v1.9.1 implemented behavior remains documented accurately.

### Out of scope

- Review CLI.
- Review schemas.
- Review run execution.
- Artifact inventory.
- Cleanup planning.
- Release-readiness integration.

---

## Phase 1: Profile Catalog Is Inspectable

**User stories covered**

- Story 1: contributors can list review profiles.
- Story 2: contributors can identify the quick profile.
- Story 3: maintainers can identify the standard profile.
- Story 4: release maintainers can identify the release profile.

**Observable behaviors**

- `agent-harness review profiles` prints the built-in profile catalog.
- `agent-harness review profiles --json` emits `review_profile_catalog.v1`.
- The catalog includes `quick`, `standard`, and `release` with command order,
  required/optional flags, expected duration class, and evidence expectations.

**First RED test**

- Run `agent-harness review profiles --json` and assert schema version,
  profile ids, command order, required flags, expected duration classes, and
  zero filesystem mutation outside normal CLI startup.

### What to build

Create the review boundary, profile catalog contract, and CLI wiring for the
read-only catalog path. This is the walking skeleton for the review command
group and must not execute any profile command.

### Acceptance criteria

- [x] `agent-harness review --help` exposes `profiles`, `status`, `run`, and
      `artifacts`, even if later commands still fail with planned diagnostics.
- [x] `review profiles` lists `quick`, `standard`, and `release`.
- [x] `review profiles --json` emits valid `review_profile_catalog.v1`.
- [x] The quick profile includes `agent-harness doctor`,
      `agent-harness docs check`, and `python -m pytest -q`.
- [x] The standard profile extends quick with Ruff, mypy, compileall,
      `agent-harness eval`, and `agent-harness template validate --all`.
- [x] The release profile extends standard with pre-commit, slow tests,
      package-check, demos, governance export, evidence pack export, and release
      readiness.
- [x] Unknown or duplicate profile ids cannot appear in the catalog.

### Out of scope

- Running profile commands.
- Inspecting existing evidence.
- Artifact inventory or cleanup planning.
- Release readiness gate changes.

---

## Phase 2: Review Status Summarizes Current State

**User stories covered**

- Story 5: reviewers can inspect existing state without running checks.
- Story 7: reviewers can distinguish required, optional, missing, and skipped
  evidence.

**Observable behaviors**

- `agent-harness review status --profile quick --json` emits `review_status.v1`
  without executing checks.
- The status reports command availability, latest known evidence refs, missing
  evidence, and next actions.
- Unknown profiles fail with clear diagnostics.

**First RED test**

- Seed a project with some existing docs-check and eval artifacts, run
  `review status --profile quick --json`, and assert the status reads existing
  evidence, reports missing quick-profile evidence, records next actions, and
  does not create release, governance, evidence-pack, or run artifacts.

### What to build

Implement read-only status aggregation for profile commands and known evidence
locations. The status path may write only its own optional review status output
when explicitly requested by the command contract; it must not execute checks.

### Acceptance criteria

- [x] `review status --profile quick` reports quick profile state.
- [x] `review status --profile standard` reports standard profile state.
- [x] `review status --profile release` reports release profile state.
- [x] `review status --json` emits valid `review_status.v1`.
- [x] Existing evidence refs are project-relative.
- [x] Missing evidence includes safe next actions.
- [x] Unknown profile returns exit code `2`.
- [x] `review status` does not execute profile commands.

### Out of scope

- Command execution.
- Cleanup planning.
- Release-readiness gate changes.

---

## Phase 3: Quick Profile Executes And Records Review Evidence

**User stories covered**

- Story 2: contributors can run a quick validation path.
- Story 6: review runs continue through failures.
- Story 8: review evidence is stored separately.

**Observable behaviors**

- `agent-harness review run --profile quick --json` executes the quick profile
  in documented order.
- The command writes `review_run.v1` under `.agent-harness/review/`.
- Failed commands do not stop later commands from running.
- The command returns nonzero when required quick-profile commands fail.

**First RED test**

- Run `review run --profile quick --json` with injected command outcomes where
  docs check fails and pytest passes. Assert all quick commands were attempted,
  `review_run.v1` was written, the result records safe output summaries, and
  the CLI exits `1`.

### What to build

Add command execution orchestration for the quick profile only. Keep command
execution simple, ordered, local, and evidence-backed. Preserve stdout/stderr
summaries without storing secrets, raw provider payloads, or absolute machine
paths.

### Acceptance criteria

- [x] Quick profile commands execute in catalog order.
- [x] Required command failures are recorded without stopping later commands.
- [x] `review_run.v1` records profile id, command statuses, return codes,
      duration, safe output summaries, evidence refs, skipped reasons, and next
      actions.
- [x] Exit code is `0` only when all required quick commands pass.
- [x] Exit code is `1` when any required quick command fails.
- [x] Exit code is `2` for invalid profile input.
- [x] Output summaries are redaction-safe.

### Out of scope

- Standard and release profile execution.
- Cleanup planning.
- Release-readiness gate changes.

---

## Phase 4: Standard And Release Profiles Execute Through Existing Commands

**User stories covered**

- Story 3: maintainers can run a standard validation path.
- Story 4: release maintainers can run release-oriented review.
- Story 9: release readiness receives the selected CI run id.

**Observable behaviors**

- `review run --profile standard` executes standard commands in documented
  order and writes `review_run.v1`.
- `review run --profile release --ci-run-id <id>` executes release commands in
  documented order and passes the CI run id to release readiness.
- Skips, missing evidence, failures, and not-applicable commands are visible in
  the review run output.

**First RED test**

- Run `review run --profile release --ci-run-id 123 --json` with injected
  command outcomes. Assert the generated release readiness command includes
  `--ci-run-id 123`, all release commands are represented, failures are
  preserved, and no tag or publish command is invoked.

### What to build

Extend review execution to standard and release profiles. Reuse existing
commands and evidence conventions. Do not reimplement release readiness,
package checks, governance export, evidence pack export, or eval behavior.

### Acceptance criteria

- [x] Standard profile extends quick and records standard command outcomes.
- [x] Release profile extends standard and records release command outcomes.
- [x] Release profile passes `--ci-run-id` to release readiness when supplied.
- [x] Release profile does not create tags, push tags, publish packages, or
      upload artifacts.
- [x] Review run evidence links existing command artifacts where available.
- [x] Release profile failures produce safe, actionable diagnostics.

### Out of scope

- Changing existing release readiness semantics.
- Publishing automation.
- Hosted CI integration beyond passing the CI run id through.

---

## Phase 5: Artifact Inventory And Dry-Run Cleanup Plan

**User stories covered**

- Story 10: maintainers can inspect generated artifact state.
- Story 11: maintainers can review dry-run cleanup candidates.
- Story 12: security reviewers can verify cleanup safety.

**Observable behaviors**

- `agent-harness review artifacts --json` writes and prints
  `artifact_inventory.v1` and `artifact_cleanup_plan.v1` references.
- The inventory classifies recognized generated artifacts and protected
  artifacts.
- The cleanup plan marks only recognized temporary or work directories older
  than the selected threshold as candidates.
- No files are deleted.

**First RED test**

- Seed `.agent-harness` with old release temp workspaces, old eval workspaces,
  current run summaries, evidence packs, dist artifacts, docs, config, and
  source files. Run `review artifacts --older-than-days 7 --json` and assert
  only old recognized temp/work directories are candidates while protected
  artifacts are listed as protected.

### What to build

Implement artifact inventory and dry-run cleanup planning for recognized
generated roots. Keep classification conservative and project-relative. Reject
absolute paths and traversal candidates. Do not add deletion flags.

### Acceptance criteria

- [x] `artifact_inventory.v1` is written under `.agent-harness/review/`.
- [x] `artifact_cleanup_plan.v1` is written under `.agent-harness/review/`.
- [x] Default cleanup threshold is 7 days.
- [x] `--older-than-days` changes the threshold.
- [x] Cleanup candidates are only recognized generated temp or work
      directories.
- [x] Run summaries, events, approvals, checkpoints, release evidence, evidence
      packs, governance exports, dist artifacts, source, docs, config, policy,
      and tracked files are protected by default.
- [x] The command never deletes files.
- [x] All reported paths are safe project-relative paths.

### Out of scope

- Actual deletion.
- Approval-gated cleanup execution.
- Arbitrary filesystem scanning.

---

## Phase 6: Release Readiness Accepts Review Evidence

**User stories covered**

- Story 4: release maintainers have a release-oriented review path.
- Story 8: review evidence is visible as part of release maturity.
- Story 13: documentation boundaries remain enforced.

**Observable behaviors**

- `agent-harness release readiness` includes a v2.0.0 review ergonomics gate.
- The gate validates existing review evidence without running review commands.
- Missing or invalid review evidence creates actionable diagnostics.

**First RED test**

- Run release readiness in a seeded v2.0.0 project with no review evidence and
  assert a pending review diagnostics entry without generating review runs.
  Then seed valid review profile, quick run, inventory, and cleanup plan
  artifacts and assert the review gate passes.

### What to build

Add a non-mutating release-readiness gate that validates existing review
artifacts. Link safe review artifacts in the readiness report and keep release
readiness as evidence validation, not review execution.

### Acceptance criteria

- [x] Release readiness reports `review` gate state.
- [x] Release readiness does not run review commands.
- [x] Missing review evidence is reported as missing evidence.
- [x] Existing review artifacts validate against v2.0.0 schemas.
- [x] Invalid review artifacts produce safe diagnostics.
- [x] Safe review artifact refs are linked.
- [x] Docs-check v2.0.0 claim guards pass.

### Out of scope

- Generating review evidence from release readiness.
- Replacing existing release-readiness gates.
- Release automation.

## Cross-Phase Invariants

- No existing public CLI command is removed or replaced.
- No existing schema or artifact contract is broken.
- Review commands do not widen policy or bypass policy-mediated behavior.
- Review commands do not approve, deny, mutate approvals, or alter policy.
- `review status` is read-only.
- `review artifacts` is dry-run only and never deletes files in v2.0.0.
- Review evidence uses project-relative paths for repository artifacts.
- Raw provider payloads, credentials, API keys, environment values, raw
  headers, private uploads, PII, customer data, secret values, and absolute
  local machine paths never enter review artifacts.
- Release readiness validates existing review evidence and never generates it.
- Tests verify behavior through public CLI commands, JSON artifacts, and
  release-readiness output.
- No subsystem is considered implemented until an observable behavior test
  exercises it through a public interface.
