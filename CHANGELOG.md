# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-04-26

Initial V0 release.

- Added the V0 CLI surface for project initialization, template application,
  task validation, dry-run and approval-bound execution, run inspection, evals,
  exports, and environment checks.
- Added deterministic run storage with JSONL audit events, context manifests,
  checkpoints, summaries, artifact indexes, and SQLite-backed inspectable
  metadata.
- Added policy-enforced context construction, denied-data blocking, redaction,
  approval binding, deterministic retrieval, and a mock runtime that consumes
  real task, context, and tool-observation inputs.
- Added local eval scorecards plus JSON, Markdown, and SARIF export support.
- Added CI coverage for lint, typecheck, unit, integration, adversarial, and
  end-to-end checks.
- Updated the GitHub Actions workflow to `actions/checkout@v6` and
  `actions/setup-python@v6` to remove the hosted-runner Node.js 20 deprecation
  warning observed on the first remote CI run.
