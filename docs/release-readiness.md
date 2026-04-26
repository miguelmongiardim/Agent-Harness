# Release Readiness

## Current Capabilities

`agent-harness release readiness --version 0.3.0` writes a local
`release_readiness.v1` report under `.agent-harness/release/`.

The report represents:

- docs gate status
- local check commands
- remote CI status fields for Python 3.11 and Python 3.12
- Python 3.13 allowed-failure status field
- advisory Gitleaks and CycloneDX report references
- changelog entry presence
- release tag target commit evidence

The command is evidence collection, not release automation. The release tag is
pushed only after local gates pass and remote blocking CI for the target commit
is verified.

## Roadmap

Automated release publishing, deployment artifacts, and compliance attestation
are outside the current release workflow.
