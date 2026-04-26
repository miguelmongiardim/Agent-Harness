# Release Readiness

## Current Capabilities

`agent-harness release readiness` writes a local
`release_readiness.v1` report under `.agent-harness/release/`.

The command defaults to `[project].version` from `pyproject.toml`. Release
managers can still bind the report to an explicit version and CI run:

```powershell
agent-harness release readiness --version 0.3.0 --ci-run-id 24962697751
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

The package install path is:

```powershell
python -m pip install .
agent-harness doctor
```

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

## Roadmap

The V3/v1.0.0 plan expands release readiness toward package, clean-install,
console script, demo, template, changelog, CI, and release-artifact evidence.
Automated release publishing, production deployment artifacts, and compliance
attestation are outside the current release workflow.
