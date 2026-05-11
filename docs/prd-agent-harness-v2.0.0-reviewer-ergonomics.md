# PRD: Agent Harness v2.0.0 Reviewer Ergonomics

v2.0.0 targets reviewer and contributor ergonomics after the v1.9.1
maintenance release. It adds a teachable local review workflow over existing
Agent Harness evidence, checks, release gates, and generated artifacts.

This PRD is planning only. Do not implement it until a separate TDD execution
request starts the first vertical slice.

## Problem Statement

Agent Harness now has a broad local evidence surface: runs, approvals, context
manifests, provider-call evidence, retrieval scorecards, templates, skills,
MCP resources, orchestration, benchmark comparisons, governance exports,
evidence packs, release readiness, docs checks, CI evidence, and demos.

The individual surfaces are intentionally inspectable, but the normal reviewer
workflow is hard to teach. A maintainer has to know which command belongs to
which review moment, which evidence is required, which checks are quick enough
for a normal contribution, and which generated directories are safe to ignore
or clean up. That friction slows review and makes local results harder to
compare with CI.

The current release checklist is complete but long. `release readiness` can
describe final release state, but it is not the same as a day-to-day review
entrypoint. `doctor`, `docs check`, `pytest`, `eval`, `benchmark`, `governance`,
`evidence`, and `release` each expose part of the story. Reviewers need one
additive command family that explains and optionally runs the right subset
without replacing the existing commands.

The affected actors are:

- contributors who need to know what to run before sending changes
- reviewers who need to see local evidence state quickly
- release maintainers who need a repeatable path from routine checks to final
  release gates
- maintainers who need generated artifact state to be understandable and safe
  to clean up later
- documentation reviewers who need v2.0.0 scope to stay additive and not
  overclaim hosted, compliance, live-provider, or destructive behavior

## Solution

Add an `agent_harness.review` boundary and `agent-harness review` command group
that coordinates existing checks and evidence into named review profiles.

The primary workflows are:

1. A contributor runs `agent-harness review profiles` to see available review
   profiles and the commands each profile represents.
2. A contributor runs `agent-harness review status --profile quick` to see the
   current local review state without executing checks.
3. A contributor runs `agent-harness review run --profile quick` before routine
   review. The command executes the quick profile, continues through failures,
   writes review evidence, and returns nonzero when required checks fail.
4. A maintainer runs `agent-harness review run --profile standard` before
   larger changes that touch public behavior or docs.
5. A release maintainer runs `agent-harness review run --profile release
   --ci-run-id <id>` to execute the release-oriented local command set and bind
   release readiness to the relevant CI run.
6. A reviewer runs `agent-harness review artifacts` to produce a redaction-safe
   artifact inventory and a dry-run cleanup plan for recognized generated
   artifact roots.

v2.0.0 preserves existing public CLI, schema, and artifact contracts. The new
review surface is additive. It delegates to existing commands where those
commands already own behavior, and it records review-specific evidence under
`.agent-harness/review/`.

The built-in profiles are:

- `quick`: `agent-harness doctor`, `agent-harness docs check`, and
  `python -m pytest -q`
- `standard`: `quick` plus Ruff, mypy, compileall, `agent-harness eval`, and
  `agent-harness template validate --all`
- `release`: `standard` plus pre-commit, slow tests, package check, demos,
  governance export, evidence pack export, and release readiness

Artifact cleanup in v2.0.0 is dry-run only. The command can inventory
recognized generated state and write a cleanup plan, but it does not delete
files. By default, cleanup candidates are recognized temporary or work
directories older than 7 days. Release evidence, run summaries, evidence packs,
dist artifacts, source files, configs, policies, and docs are never cleanup
candidates by default.

## User Stories

1. As a contributor, I want to list review profiles, so that I know which
   checks are expected before review.
2. As a contributor, I want a quick profile, so that routine changes have a
   fast and consistent local validation path.
3. As a maintainer, I want a standard profile, so that public behavior and docs
   changes can be checked more thoroughly without jumping to full release
   gates.
4. As a release maintainer, I want a release profile, so that final release
   evidence can be executed through one teachable local entrypoint.
5. As a reviewer, I want `review status` to summarize existing evidence without
   running checks, so that I can inspect state safely.
6. As a reviewer, I want review runs to continue through failures, so that one
   failed command does not hide later missing evidence.
7. As a reviewer, I want review output and JSON evidence to show required,
   optional, failed, skipped, and missing checks distinctly, so that next
   actions are clear.
8. As a maintainer, I want review evidence stored under a dedicated review
   artifact root, so that review results are reproducible and separate from
   release readiness.
9. As a release maintainer, I want the release profile to pass `--ci-run-id`
   through to release readiness, so that readiness can bind to a specific CI
   run.
10. As a maintainer, I want an artifact inventory, so that generated state is
    visible without manually inspecting `.agent-harness`.
11. As a maintainer, I want dry-run cleanup planning, so that stale generated
    work directories can be reviewed before any future deletion feature exists.
12. As a security reviewer, I want cleanup planning to be conservative and
    path-safe, so that source files, configs, policies, docs, release evidence,
    evidence packs, and run summaries are not marked for deletion.
13. As a documentation reviewer, I want docs checks to reject unsupported v2.0.0
    scope claims, so that the release is not described as hosted, destructive,
    compliance-certifying, live-provider expansion, or MCP execution work.

## Behavioral Requirements

1. `agent-harness review profiles` lists the built-in `quick`, `standard`, and
   `release` profiles.
2. `agent-harness review profiles --json` emits a `review_profile_catalog.v1`
   payload.
3. Each profile record includes profile id, title, description, commands,
   required/optional status, expected duration class, evidence expectations,
   and whether the command mutates generated artifacts.
4. `agent-harness review status --profile <name>` reads current project state
   and writes no source, config, policy, release, governance, evidence-pack, or
   run artifacts.
5. `review status` reports command availability, latest known evidence refs,
   missing evidence, profile command status, and next actions.
6. `review status --json` emits a `review_status.v1` payload.
7. `review status` fails with a clear diagnostic for an unknown profile.
8. `agent-harness review run --profile quick` executes the quick profile
   commands in documented order.
9. `agent-harness review run --profile standard` executes the standard profile
   commands in documented order.
10. `agent-harness review run --profile release` executes the release profile
    commands in documented order.
11. Review runs continue after failed commands and record all command results.
12. Review runs return exit code `0` only when all required commands for the
    selected profile pass or are explicitly not applicable.
13. Review runs return exit code `1` when one or more required commands fail.
14. Review runs return exit code `2` for invalid inputs such as unknown
    profiles or invalid option combinations.
15. Review runs write `review_run.v1` evidence under `.agent-harness/review/`.
16. `review_run.v1` records profile id, command list, command status, return
    codes, start/end timestamps, duration, safe stdout/stderr summaries,
    evidence refs, skipped reasons, and next actions.
17. Review run evidence uses project-relative paths for repository artifacts.
18. Review run output never stores environment variable values, credentials,
    raw provider payloads, raw headers, private uploads, or absolute local
    machine paths.
19. The release profile accepts `--ci-run-id <id>` and passes it through to
    `agent-harness release readiness --ci-run-id <id>`.
20. The release profile does not create release tags, push tags, publish
    packages, or upload artifacts beyond existing command behavior.
21. `agent-harness review artifacts` writes `artifact_inventory.v1` and
    `artifact_cleanup_plan.v1` under `.agent-harness/review/`.
22. Artifact inventory covers recognized generated roots, including
    `.agent-harness` subdirectories used for release temp workspaces, eval work,
    benchmark workspaces, retrieval indexes, governance exports, evidence
    packs, review evidence, and run artifacts.
23. Artifact inventory records safe project-relative paths, artifact kind,
    size where available, modified time where available, and whether the
    artifact is protected from cleanup.
24. The cleanup plan is dry-run only in v2.0.0.
25. The cleanup planner marks only recognized generated temporary or work
    directories older than the selected age threshold as cleanup candidates.
26. The default cleanup age threshold is 7 days.
27. `--older-than-days <n>` changes the cleanup candidate age threshold without
    changing protected artifact classes.
28. Release evidence JSON, run summaries, event logs, approval records,
    checkpoints, evidence packs, governance exports, dist artifacts, source
    files, configs, policies, docs, and tracked repository files are protected
    by default.
29. Cleanup planning rejects path traversal and absolute path candidates.
30. Cleanup planning never deletes files in v2.0.0.
31. Release readiness gains a non-mutating v2.0.0 review ergonomics gate after
    review evidence is implemented.
32. The release-readiness review gate checks for a valid profile catalog, a
    recent quick profile review run, a redaction-safe artifact inventory, and a
    dry-run cleanup plan.
33. Documentation identifies v2.0.0 as planned until behavior is implemented
    and tested.
34. Docs checks reject claims that v2.0.0 provides hosted operation, MCP tool
    execution, production retrieval, live provider expansion, compliance
    certification, destructive cleanup, or replacement of existing release
    readiness unless those claims are clearly out of scope, roadmap-only, or
    denied.

## Implementation Decisions

- Add `agent_harness.review` as the v2.0.0 boundary. It owns profile catalog
  construction, review status aggregation, review run evidence, artifact
  inventory, and dry-run cleanup planning.
- Add a top-level `agent-harness review` CLI group with `profiles`, `status`,
  `run`, and `artifacts`.
- Keep review orchestration local and command-backed. Existing commands keep
  ownership of their behavior and artifacts.
- Use additive StrictModel contracts for `review_profile_catalog.v1`,
  `review_status.v1`, `review_run.v1`, `artifact_inventory.v1`, and
  `artifact_cleanup_plan.v1`.
- Store review evidence under `.agent-harness/review/`.
- Keep `review status` read-only. It may inspect existing evidence but must not
  execute checks or generate release evidence.
- Allow `review run` to write review evidence and any normal artifacts produced
  by the commands it executes.
- Keep `review artifacts` non-destructive in v2.0.0. It writes inventory and a
  dry-run cleanup plan only.
- Use existing safe path, JSON writing, timestamp, subprocess, docs-check,
  release, eval, benchmark, governance, evidence, and storage patterns where
  they fit the public behavior.
- Treat existing release readiness as the final release gate. Review commands
  make the path easier to run and understand, but do not replace release
  readiness.
- Preserve the v1.0.0 compatibility and deprecation contract. Existing public
  CLI, schema, and artifact contracts remain valid.
- Do not add config schema for v2.0.0 profile customization. Profiles are
  built in for the initial release.

## Testing Decisions

- Test review behavior through public CLI commands and persisted review
  artifacts.
- Unit tests should cover profile catalog validation, review schema contracts,
  command status aggregation, exit-code mapping, safe output summarization,
  artifact classification, protected artifact classes, age threshold behavior,
  and path safety.
- Integration tests should cover `review profiles`, `review status`,
  `review run --profile quick`, `review run --profile standard` with injected
  command outcomes, `review run --profile release --ci-run-id <id>`, and
  `review artifacts`.
- Regression tests should prove cleanup planning never marks tracked files,
  source files, docs, configs, policies, release evidence, evidence packs, run
  summaries, events, approvals, checkpoints, or dist artifacts as cleanup
  candidates.
- Docs-check tests should guard against unsupported v2.0.0 claims.
- Release-readiness tests should require v2.0.0 review evidence only after the
  review feature is implemented.
- Tests should not assert private helper names. They should verify behavior
  through CLI output, JSON artifacts, release readiness output, and safe
  project-relative paths.

## Out of Scope

- Implementing v2.0.0 in this planning task.
- Replacing existing `doctor`, `docs check`, `eval`, `benchmark`,
  `governance`, `evidence`, or `release readiness` behavior.
- Breaking existing CLI commands, schema versions, or artifact shapes.
- User-configurable review profiles in config files.
- Hosted APIs, remote operator deployments, multi-user identity, cloud
  services, or production web operation.
- Live provider expansion, new provider transports, or fixture capture tooling.
- MCP tools, MCP writes, MCP execution, or hosted MCP behavior.
- Production retrieval, remote embeddings, hosted embedding providers, or cloud
  vector databases.
- Formal compliance certification, auditor approval, regulatory compliance,
  or control effectiveness claims.
- Actual artifact deletion, pruning, or destructive cleanup.
- Publishing packages, creating tags, pushing tags, or uploading artifacts from
  review commands.
- Scanning arbitrary filesystem locations outside recognized project artifact
  roots.

## Further Notes

The main product tradeoff is adding one new `review` command group instead of
spreading reviewer guidance across existing commands. The new command group is
justified because the workflow is cross-cutting and teachability is the core
problem.

The main implementation risk is duplicating release readiness. The review
boundary should coordinate and summarize; release readiness remains the final
release control surface.

The main safety risk is cleanup planning. v2.0.0 deliberately stops at dry-run
plans because destructive cleanup needs its own approval and safety design.

The first implementation should prove the smallest public behavior:
`agent-harness review profiles --json` returns the built-in profile catalog
without touching any existing feature behavior.
