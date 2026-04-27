# Release Readiness

## Current Capabilities

`agent-harness release readiness` writes a local
`release_readiness.v1` report under `.agent-harness/release/`.

The command defaults to `[project].version` from `pyproject.toml`. Release
managers can still bind the report to an explicit version and CI run:

```powershell
agent-harness release readiness --version 1.0.0 --ci-run-id <run-id>
```

When GitHub CLI is authenticated, the command attempts to discover the latest
`CI` workflow run for the release target commit.

Package and clean-install evidence is generated with:

```powershell
agent-harness release package-check
```

The local development install path remains:

```powershell
uv sync --extra dev
uv run agent-harness doctor
```

Contributor hygiene is available through the local pre-commit config:

```powershell
python -m pre_commit run --all-files
```

The hooks run Ruff lint/format checks, mypy, docs check, compileall, a large
file guard, and a private key guard. They use local hooks so normal contributor
checks do not depend on optional advisory scanner installs.

CI keeps advisory evidence visible with optional Gitleaks and CycloneDX/SBOM
outputs under `.agent-harness/advisories/`. Those reports are useful review
inputs, but advisory tooling is optional and must not block required CI when the
tools are absent.

The package install path is:

```powershell
python -m pip install .
agent-harness doctor
```

The Docker path is local/demo reproducibility packaging, not production
deployment:

```powershell
docker build -t agent-harness:local .
docker run --rm agent-harness:local agent-harness demo provider-audit
```

CI runs the same Docker build and provider-audit demo command in a dedicated
Docker demo job.

Required demo evidence is generated with:

```powershell
agent-harness demo provider-audit
agent-harness run examples/tasks/python_refactor.json --dry-run
```

Those commands record `.agent-harness/release/evidence/demo-provider-audit.json`
and `.agent-harness/release/evidence/demo-python-refactor.json`. The
provider-audit demo remains the main reproducible walkthrough; Python refactor
remains the secondary dry-run demo.

The report represents:

- package build evidence
- clean-install evidence
- installed console-script evidence
- required demo evidence
- docs gate status
- schema compatibility documentation presence
- roadmap-claim docs status
- bundled template validation evidence
- release artifact presence
- local check commands
- remote CI run evidence for the target commit
- remote CI status fields for Python 3.11 and Python 3.12
- Python 3.13 allowed-failure status field
- advisory Gitleaks and CycloneDX report references
- changelog entry presence
- release tag target commit evidence
- actionable diagnostics for missing or failed evidence

The command is evidence collection, not release automation. A report is `ready`
only when required package, install, console script, demo, docs, changelog,
template, artifact, tag, and remote CI evidence is present and passing.

## Release Checklist

Before tagging v1.0.0:

1. Run `uv sync --extra dev`.
2. Run `python -m pre_commit run --all-files`.
3. Run `python -m pytest -q`.
4. Run `agent-harness release package-check`.
5. Run `agent-harness demo provider-audit`.
6. Run `agent-harness run examples/tasks/python_refactor.json --dry-run`.
7. Run `agent-harness template validate --all`.
8. Run `agent-harness eval`.
9. Run `agent-harness release readiness --version 1.0.0`.
10. Confirm CI passes for the release commit.

## Tag Process

Create the release tag only after the release commit is pushed and required CI
has passed for that exact commit:

```powershell
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
agent-harness release readiness --version 1.0.0 --ci-run-id <run-id>
```

The readiness report binds the tag target commit to the recorded GitHub Actions
run. A report is not ready when the run is missing, failed, or points at a
different commit.

## Artifact Verification

`agent-harness release package-check` records wheel and source distribution
hashes in `.agent-harness/release/package-check.json` and supporting evidence
files under `.agent-harness/release/evidence/`. Reviewers should verify that:

- `dist/agent_harness-1.0.0-*.whl` exists.
- `dist/agent_harness-1.0.0.tar.gz` exists.
- package-check evidence reports `status: passed`.
- clean-install evidence reports `status: passed`.
- console-script evidence reports `status: passed`.
- the final readiness report is generated for `version: 1.0.0`.

## Roadmap

Automated release publishing, production deployment artifacts, and compliance
attestation are outside the current release workflow.
