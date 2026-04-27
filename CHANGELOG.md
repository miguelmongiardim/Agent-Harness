# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- No changes yet.

## [1.1.0] - 2026-04-27

V4 Provider Core release.

- Added strict `provider_action_envelope.v1` validation before runtime action
  planning, so malformed provider output, refusals, unsupported responses,
  unknown tools, and invalid tool arguments fail before tool execution.
- Added pre-provider-use profile validation for endpoint env vars, API-key env
  vars, transport, trust zone, network flags, live opt-in, and
  approval-compatible policy without storing credential values.
- Added a narrow opt-in OpenAI-compatible live smoke path behind existing
  provider-use approval, provider-input, action-envelope, and artifact
  boundaries.
- Added provider-call evidence binding approval ids, provider-input hash,
  action-envelope hash, checkpoint hash, mode, latency, token metrics when
  available, and redacted prompt/response artifact references.
- Added deterministic provider-core eval coverage for mock and recorded-fixture
  paths, malformed output rejection, unauthorized tool denial, hard-deny
  provider-input exclusion, approval drift blocking, redacted evidence, and
  live-smoke skip behavior.
- Documented Provider Core setup, safety boundaries, recorded fixture
  expectations, live smoke behavior, and V4 out-of-scope work.

## [1.0.0] - 2026-04-27

V3 maturity release.

- Added the v1.0.0 public compatibility and deprecation policy for core CLI
  commands, public schemas, run artifacts, and bundled template manifests.
- Expanded `agent-harness release readiness` into the release control surface
  for package, clean-install, console-script, demo, docs, template, changelog,
  artifact, tag, and GitHub Actions CI evidence.
- Added `agent-harness release package-check` for wheel/sdist build evidence,
  clean wheel installation, installed console-script `doctor`, and artifact
  hashes.
- Added the stable `agent-harness demo provider-audit` golden path and kept the
  deterministic Python refactor dry-run as the secondary demo.
- Added bundled template validation with `agent-harness template validate --all`
  and clean empty-destination scaffolding without weakening overwrite and
  policy protections.
- Added local pre-commit discipline, required CI release gates, optional
  advisory scanner evidence, and Docker local/demo reproducibility packaging.
- Documented migration from v0.3.0 to v1.0.0, release checklist, tag process,
  artifact verification, and clear Implemented vs Roadmap boundaries.

## [0.3.0] - 2026-04-26

V2 completion release.

- Added public V2 defaults for `config.v2`, `task.v2`, `policy.v2`, and
  `template.v2`, with compatibility loading and non-widening migration reports
  for readable v1 inputs.
- Added first-class `policy.v2` provider-input, trust-zone, approval, scanner,
  template capability, and migration policy sections.
- Added approval-bound provider-use evidence with provider profile, trust zone,
  model id, provider-input hash, policy decision id, and checkpoint binding.
- Added provider-call audit artifacts with approval ids, prompt/response hashes,
  redacted summaries, token/latency metrics, and policy decision references
  without storing raw provider payloads by default.
- Added security gate evidence, advisory Gitleaks/CycloneDX report discovery,
  SARIF security properties, and doctor warnings for optional advisory tools.
- Hardened retrieval defaults so lexical remains deterministic, local dense
  retrieval is opt-in through local fixtures, missing Qdrant/FastEmbed
  dependencies fall back cleanly, and remote embeddings remain out of scope.
- Added `template.v2` compatibility metadata and the Python trio templates:
  `python-lib`, `cli-tool`, and `fastapi-service`.
- Added benchmark adapter evidence for SWE-bench-style and terminal-task
  miniature sample packs, including a local dense-retrieval sample whose
  benchmark result points to real run evidence.
- Added `examples/provider_audit/` as the main V2 walkthrough for offline
  provider-use approval, inspectable provider-input policy evidence, redacted
  provider-call artifacts, and JSON/Markdown/SARIF exports.
- Added release-readiness reporting for docs gates, local checks, CI evidence
  fields, advisory report references, changelog entries, and tag target
  evidence.

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
