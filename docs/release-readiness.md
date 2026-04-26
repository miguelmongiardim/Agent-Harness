# Release Readiness

## Current Capabilities

`agent-harness release readiness --version 0.3.0` writes a local
`release_readiness.v1` report under `.agent-harness/release/`.

When GitHub CLI is authenticated, the command attempts to discover the latest
`CI` workflow run for the release target commit. Release managers can bind the
report to a known run explicitly:

```powershell
agent-harness release readiness --version 0.3.0 --ci-run-id 24962697751
```

The report represents:

- docs gate status
- local check commands
- remote CI run evidence for the target commit
- remote CI status fields for Python 3.11 and Python 3.12
- Python 3.13 allowed-failure status field
- advisory Gitleaks and CycloneDX report references
- changelog entry presence
- release tag target commit evidence

The command is evidence collection, not release automation. A report is `ready`
only when docs pass, the changelog entry exists, the release tag is pushed, and
the required remote Python 3.11 and 3.12 compatibility jobs are recorded as
passing for the tag target commit.

## Roadmap

Automated release publishing, deployment artifacts, and compliance attestation
are outside the current release workflow.
