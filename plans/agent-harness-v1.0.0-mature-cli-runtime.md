# Agent Harness v1.0.0 / v1.0.0 Plan

## Planning Decision

v1.0.0 is the v1.0.0 Mature CLI/runtime track. The goal is to turn the v0.3.0
architecture-completion prototype into a stable OSS CLI/runtime release with
auditable release evidence, reproducible demos, packaging checks, Docker demo
packaging, pre-commit discipline, accurate public docs, and a clear
compatibility contract.

v1.0.0 does not promote deferred platform scope. Enterprise readiness, compliance
readiness, MCP support, multi-agent support, production Qdrant server mode,
external catalogs, web/API maturity, and deployment hardening remain out of
scope until later plans implement and test them.

## Phase 0: v1.0.0 PRD, Compatibility Contract, And Scope Reset

First RED test: docs check fails until v1.0.0 docs define v1.0.0 positioning,
compatibility rules, and Implemented vs Roadmap boundaries.

Acceptance criteria:

- PRD and plan are written.
- README, roadmap, architecture, security, and release docs stop implying
  deferred platform features.
- Compatibility and deprecation policy are documented.
- Existing docs-check passes.

## Phase 1: Release Readiness As The Control Surface

First RED test: `agent-harness release readiness` fails on missing
package/demo/template/docs evidence and passes only when required evidence is
present.

Acceptance criteria:

- Readiness checks package build, clean install, console script, demos, docs,
  changelog, roadmap claims, templates, and artifacts.
- Readiness defaults to current package version.
- Missing evidence produces actionable diagnostics.

## Phase 2: Packaging And Clean Install Golden Path

First RED test: package build plus clean environment install cannot run the
console script and doctor command until packaging is fixed.

Acceptance criteria:

- Wheel and sdist build cleanly.
- Clean install succeeds.
- Installed `agent-harness` console script works.
- Release artifacts are present and verifiable.
- Install paths using `uv sync` and package install are documented.

## Phase 3: Demo Command And Local Golden Path

First RED test: the documented provider-audit golden path fails until
`agent-harness demo provider-audit` creates a run and returns an inspectable run
id.

Acceptance criteria:

- Local golden path works exactly as documented.
- Provider audit remains the main demo.
- Python refactor remains the secondary demo.
- Required demos emit inspectable artifacts.
- Provider audit eval path works.

## Phase 4: Template Maturity Without Clean-Workspace Approval

First RED test: bundled template validation and clean-workspace application fail
until every bundled template can be validated and applied cleanly without
approval.

Acceptance criteria:

- Every bundled template can be listed, shown, validated, applied to a clean
  workspace, and documented.
- Clean empty-destination scaffolding does not pause for approval.
- Overwrite, non-empty destination, or risky mutation paths still require
  policy/approval.
- Release readiness validates bundled templates.

## Phase 5: Pre-commit And CI Maturity

First RED test: CI lacks pre-commit, packaging, demo, and release-artifact
checks until dedicated jobs are added.

Acceptance criteria:

- Pre-commit config exists and is documented.
- CI runs required tests, docs checks, packaging checks, demo validation,
  template validation, and release artifact checks.
- Advisory scanners/SBOM remain visible without making normal local workflows
  brittle.
- Required CI stays stable.

## Phase 6: Docker Golden Path

First RED test: Docker build or provider-audit demo command fails until the
Dockerfile supports the documented local demo.

Acceptance criteria:

- Docker image builds.
- Docker provider-audit golden path works.
- Docs state Docker is local/demo reproducibility packaging, not production
  deployment.
- Docker validation is included in CI or release readiness where practical.

## Phase 7: v1.0.0 Release Closure

First RED test: release readiness for 1.0.0 fails until changelog, version,
migration notes, docs, artifacts, demos, templates, and CI evidence are
complete.

Acceptance criteria:

- Version is bumped to 1.0.0.
- Changelog has 1.0.0 entry.
- Migration notes from v0.3.0 to v1.0.0 exist.
- Release checklist, tag process, and artifact verification are documented.
- `agent-harness release readiness` reports ready when tag and CI evidence are
  present.
- No docs claim enterprise readiness, compliance readiness, MCP support,
  multi-agent support, production Qdrant server mode, external catalogs, or
  web/API platform maturity.

## TDD Rules

- Each phase starts with one failing public-interface test.
- Implement only enough behavior to make the current test green.
- Refactor only after green.
- Do not add horizontal infrastructure unless the current or next slice
  exercises it.
- Do not implement roadmap features without an observable behavior and
  acceptance test.
- Tests verify CLI/runtime behavior through public interfaces, not private
  function names.

## Cross-Phase Invariants

- Policy remains the permission ceiling.
- Run artifacts remain inspectable and reviewable.
- Public docs match implemented behavior.
- Default workflows remain local-first and credential-free.
- Optional tools may improve evidence but must not break normal local
  development when absent.
- Roadmap features stay clearly marked until implemented and tested.
