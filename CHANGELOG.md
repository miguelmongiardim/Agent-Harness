# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- No changes yet.

## [1.7.0] - 2026-04-30

V11 Policy-Mediated Multi-Agent Orchestration release.

- Added local, sequential `orchestration.v1` supervision over normal child
  `task.v2` dry-run executions, with explicit `policy.v2.orchestration`
  enablement and role ceilings for planner, implementer, reviewer, and tester.
- Added aggregate orchestration evidence for summaries, events, manifests,
  artifact indexes, generated dependency handoffs, effective child authority,
  supervisor plan approvals, approval-bound resume, child pause/failure
  propagation, and safe JSON exports.
- Added read-only MCP resources for orchestration summary, manifest, events,
  children, and handoffs, with metadata-only access logs and no MCP tools or
  execution surface.
- Added `examples/orchestration_workflow/` as the V11 golden path and expanded
  release readiness to verify orchestration demo, policy, artifacts,
  inspect/export, MCP resource reads, and MCP access-log evidence.

## [1.6.1] - 2026-04-29

V10 Schema Boundary maintenance release.

- Moved Pydantic contracts from the root `agent_harness.schemas` surface into
  owner package schema modules for tasks, config, policy, tools, model,
  context, storage, templates, skills, evals, benchmarks, MCP, operator,
  security, and runtimes.
- Removed the transitional `agent_harness.schemas` import facade and added
  tests preventing the root schema module from returning.
- Preserved CLI behavior, persisted artifact schemas, schema evidence, and
  legacy public input compatibility while changing only Python import
  ownership.
- Split slow provider, retrieval, release-evidence, and e2e golden-path tests
  out of the default pytest profile so contributor validation remains
  practical while release gates stay explicit.

## [1.6.0] - 2026-04-29

V9 MCP Boundary release.

- Added a local, optional, read-only MCP boundary under `agent_harness.mcp`
  exposing policy-filtered resources and deterministic review prompts.
- Added SDK-independent MCP CLI inspection for resources and prompts, with
  safe denial envelopes and metadata-only `mcp_access_log.v1` evidence.
- Added an optional stdio MCP server backed by the existing resource and prompt
  registries, advertising resources and prompts only with no tools capability.
- Added `examples/mcp_boundary/` as the V9 golden path with expected resource,
  prompt, and denied-resource examples.
- Expanded release readiness and CI to verify the MCP extra, CLI behavior,
  denied resources, access evidence, and stdio resources/prompts-only protocol
  behavior.

## [1.5.0] - 2026-04-28

V8 Skills System release.

- Added local, versioned, validated Markdown skills as policy-mediated workflow
  guidance with bundled and explicitly configured local sources.
- Added `agent-harness skill list/show/validate/render/resolve` and
  `agent-harness skill pack validate` for skill discovery, inspection,
  deterministic hashing, compatibility checks, and local pack validation.
- Added bundled `write-a-prd`, `prd-to-plan`, `tdd`, and
  `prd-plan-tdd-workflow` skills.
- Added `config.v2` `skills.local_dirs`, `task.v2` requested skills, and
  `template.v2` recommended skill evidence without letting skills widen tools,
  policies, approvals, provider profiles, or execution authority.
- Added policy-gated skill context provenance and `skill_manifest.v1` run
  artifacts linked from summaries, artifact indexes, inspect output, operator
  run detail, and eval expected-skill assertions.
- Added `examples/skills_workflow/` as the V8 golden path and expanded release
  readiness to verify bundled skill validation, skill registry commands, task
  resolution, dry-run manifest emission, context provenance, inspect output,
  skills docs, and deferred-scope docs hygiene.

## [1.4.0] - 2026-04-28

V7 Template Pack System release.

- Added local-first `template.v2.toml` template packs with bundled and
  configured local-pack discovery while preserving legacy bundled JSON
  readability.
- Added shared template-pack validation for bundled and local packs, including
  path safety, placeholder safety, generated example schema checks, and
  explicit denials for remote sources, hooks, scripts, private upload
  references, and secret-like generated content.
- Added deterministic parameter rendering for declared `{{ param_name }}`
  placeholders in generated text and relative target paths.
- Added dry-run and preview-diff template apply modes that emit
  `template_application.v1` plan evidence without mutating targets, run
  artifacts, application evidence, or workspace metadata.
- Added clean empty-target apply evidence with rollback on safe write failures,
  `template_application.v1` records, and workspace metadata references.
- Added bundled V7 packs for `python-lib`, `cli-tool`, `fastapi-service`,
  `provider-audit`, and `retrieval-quality`, each with docs, demo metadata,
  and generated config/policy/task/eval examples.
- Added `examples/template_pack_system/` as the V7 golden path and expanded
  release readiness to validate, dry-run, clean-apply, schema-check, docs-check,
  and evidence-check all bundled packs while rejecting remote template catalog
  defaults.

## [1.3.0] - 2026-04-28

V6 Local Operator Surface release.

- Added the optional `agent-harness[operator]` extra with FastAPI/Uvicorn
  dependencies while keeping the base install CLI-first.
- Added `agent-harness serve`, a loopback-only local operator server that
  rejects non-loopback hosts and uses an in-memory operator token by default.
- Added a token-protected local operator API for run listing, run detail,
  context manifest inspection, policy summaries, approval listing, and
  approve/deny decisions routed through the existing approval service.
- Added packaged offline static operator UI assets with no Node build, CDN,
  remote fonts, analytics, external API calls, or persisted browser token
  storage.
- Preserved V6 mutation boundaries: no run creation, config editing, template
  application, direct patch/commit/provider execution, MCP, multi-agent
  orchestration, hosted API claim, enterprise auth claim, or compliance claim.
- Added release-readiness and CI evidence for operator app import, API smoke,
  token enforcement, loopback host rejection, approval binding protection, and
  static UI packaging.

## [1.2.0] - 2026-04-27

V5 Local-First Retrieval Hardening release.

- Added local retrieval index lifecycle commands for lexical, deterministic
  dense, hybrid, qdrant-local, and loopback-only qdrant-server indexes.
- Added local FastEmbed/Qdrant retrieval evidence with model/cache metadata,
  persistent local Qdrant storage, loopback-only server diagnostics, and
  explicit `remote_embeddings: false` evidence.
- Wired configured retrieval indexes into runtime context assembly so lexical,
  dense, and both-provenance items flow through policy and sensitivity gates
  before provider input.
- Added retrieval scorecards with Precision@k, Recall@k, backend comparison,
  per-query hits/misses/unexpected accepted chunks, policy-filtered rejected
  chunks, and release-readiness evidence.
- Added the `examples/retrieval_quality/` golden path with local-first config,
  policy-filtered public/internal fixtures, qdrant-local hybrid query evidence,
  scorecard output, and context-manifest rejection proof.
- Hardened config validation so remote embeddings, hosted embedding providers,
  cloud/API-key-backed/HTTPS/non-loopback Qdrant endpoints, and remote retrieval
  defaults are rejected or kept out of executable examples.

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
