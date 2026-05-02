# Agent Harness v1.0.0 / v1.0.0 PRD

## Status

Agent Harness v1.0.0 is the v1.0.0 Mature CLI/runtime release. It converts the v0.3.0
architecture-completion prototype into the first stable CLI/runtime release for
controlled, auditable, policy-aware agentic software-engineering workflows.

v1.0.0 means stable local OSS release discipline: stable core CLI, documented
public schema compatibility, package installation checks, reproducible demos,
release-readiness evidence, Docker demo packaging, pre-commit discipline,
accurate docs, and clear roadmap boundaries.

v1.0.0 does not mean enterprise readiness, compliance readiness, MCP support,
multi-agent support, production Qdrant server mode, external catalogs, or a
web/API platform.

## User Stories

1. As a new reviewer, I want to clone, install, run the demo, inspect
   artifacts, and run checks, so that I can evaluate Agent Harness without
   hidden setup.
2. As a maintainer, I want `agent-harness release readiness` to verify package,
   docs, demos, templates, artifacts, and release metadata, so that v1.0.0 has
   reviewable evidence.
3. As a user, I want stable core CLI commands and documented schema
   compatibility, so that workspaces are not broken casually after v1.0.0.
4. As a contributor, I want pre-commit, CI, packaging, and docs gates, so that
   routine changes preserve release quality.
5. As a template user, I want every bundled template listed, shown, validated,
   applied to a clean workspace, and documented, so that scaffolding is
   trustworthy.
6. As a demo user, I want local and Docker golden paths, so that the main
   workflow is reproducible outside the maintainer's machine.
7. As a security-minded reviewer, I want implemented behavior clearly separated
   from roadmap behavior, so that no enterprise or compliance claim is implied.

## Behavioral Requirements

1. `uv sync`, `uv run agent-harness doctor`,
   `uv run agent-harness demo provider-audit`, `inspect`, `eval`, and
   `release readiness` work from a clean checkout.
2. `docker build -t agent-harness:local .` and
   `docker run --rm agent-harness:local agent-harness demo provider-audit`
   work as the documented Docker golden path.
3. `agent-harness release readiness` checks package build, clean install,
   console script, required demos, docs, changelog, roadmap claims, bundled
   template validation, and release artifacts.
4. Core CLI commands are stable for `init`, `template`, `task validate`,
   `ingest`, `run`, `approve`, `inspect`, `eval`, `benchmark`, `export`,
   `doctor`, `docs check`, `migrate schemas`, `demo`, and
   `release readiness`.
5. After v1.0.0, breaking changes to core CLI commands, public schemas, run
   artifact formats, or template manifests require a documented deprecation
   path unless a security issue forces immediate change.
6. Normal clean-workspace template scaffolding does not require approval.
   Approval remains required for overwrites, non-empty destinations, or
   higher-risk mutations.
7. All public docs include accurate Implemented vs Roadmap separation where
   capability claims are made.

## Implementation Decisions

- Add `agent-harness demo provider-audit` as the stable main demo wrapper around
  the existing provider audit workflow.
- Add public `agent-harness template validate <template-id|--all>` behavior used
  by release readiness.
- Extend `agent-harness release readiness` so it defaults to the current package
  version while still allowing explicit evidence options such as `--version` and
  `--ci-run-id`.
- Add a Dockerfile for local/demo reproducibility only, not production
  deployment.
- Add `.pre-commit-config.yaml` with Ruff lint/format, type/check hygiene, docs
  checks, and basic secret/large-file guards.
- Keep v0.3.0 schemas as the v1.0.0 public compatibility baseline.

## Compatibility And Deprecation Policy

The v1.0.0 public compatibility baseline is:

- CLI: `init`, `template list/show/validate/apply`, `task validate`, `ingest`,
  `run`, `approve`, `inspect`, `eval`, `benchmark`, `export`, `doctor`,
  `docs check`, `migrate schemas`, `demo provider-audit`, and
  `release readiness`.
- Public schemas: `config.v2`, `task.v2`, `policy.v2`, and `template.v2`.
- Run evidence: summary, event log, artifact index, context manifest,
  checkpoints, approval records, provider-input/provider-call evidence when
  present, security findings, and exports.
- Template manifests: bundled `template.v2` manifests and readable
  `template.v1` compatibility paths.

After v1.0.0, breaking changes to those surfaces require:

- a documented replacement path,
- a migration note or command when data files are affected,
- at least one release cycle of warning where practical, and
- regression coverage through public CLI/runtime behavior.

Security fixes may make immediate breaking changes when preserving the old
behavior would expose users to a material safety issue. Those changes still
need release notes explaining the break.

## Implemented vs Roadmap

Implemented in v1.0.0:

- local-first CLI/runtime workflows,
- v0.3.0 public schema compatibility baseline,
- deterministic provider-audit and Python-refactor demos,
- policy-mediated provider input, approvals, templates, context, and exports,
- release-readiness evidence for local package/demo/docs/template gates,
- Docker packaging for local demo reproduction, and
- pre-commit and CI gates for normal contributor hygiene.

Roadmap or explicitly out of scope for v1.0.0:

- enterprise or compliance readiness,
- MCP resource/tool flows,
- multi-agent orchestration,
- production Qdrant server mode,
- external template catalogs,
- hosted web/API platform,
- remote embeddings, and
- deployment hardening.

## Major Risks

- Release readiness can become theater if it only lists commands. v1.0.0 should
  include check outputs or actionable missing-evidence diagnostics.
- Docker and package checks can become slow or brittle if default workflows
  depend on optional tools. Optional evidence should be visible without breaking
  ordinary local development.
- Clean-workspace template scaffolding must not weaken overwrite protections.
  The no-approval path is limited to empty destinations with no pre-existing
  target files.
