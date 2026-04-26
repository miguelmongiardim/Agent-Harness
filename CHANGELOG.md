# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-26

V1 release.

- Added configured provider profiles, explicit trust-zone policy, provider-use
  approvals, and provider-input sensitivity gates with inspectable evidence.
- Added recorded provider gateway support for mock, OpenAI-compatible, and
  Anthropic transports without leaking endpoint or API-key values into run
  artifacts.
- Added hybrid lexical and local dense retrieval provenance through
  `context_manifest.v2`, including included and rejected evidence.
- Added packaged template registry metadata plus approval-bound template apply
  with workspace metadata recording.
- Added separate approval-bound `git_commit` planning and execution with parent
  HEAD, file set, content hash, diff hash, message hash, policy, and checkpoint
  bindings.
- Added bundled benchmark sample packs, benchmark result artifacts, security
  findings with pre-run gates, SARIF finding export, and doctor scanner
  reporting.
- Added the optional LangGraph boundary proof behind the `langgraph` extra,
  preserving the native runtime as the primary execution path.
- Updated release hygiene so generated benchmark and eval work artifacts stay
  out of git status.

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
