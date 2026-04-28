# Agent Harness

Agent Harness is a portfolio-grade, enterprise-inspired Python CLI for
controlled agent workflow experiments. The current implementation demonstrates policy-gated software
engineering runs with deterministic mock agents, explicit context manifests,
approval binding, audit logs, evals, and reproducible local artifacts.

The project is intentionally not enterprise-ready. It is designed toward enterprise
concerns such as permission ceilings, auditability, approval checkpoints,
context provenance, and reportable evidence, without claiming production
assurance.

## What This Repo Proves

- A deterministic mock model consumes real task specs, context evidence, and
  tool observations before proposing actions.
- Context, retrieval, tool calls, approvals, exports, and runtime decisions all
  pass through policy evaluation.
- Policy profiles are permission ceilings. Tasks and CLI flags can narrow
  permissions, but cannot widen them.
- Retrieved content, issue text, model output, tool output, and external data
  are treated as untrusted evidence.
- Runs produce append-only JSONL events, context manifests, checkpoints,
  approval records, summaries, and exportable JSON, Markdown, and SARIF.

## Quick Start

```powershell
uv sync --extra dev
uv run agent-harness doctor
uv run agent-harness demo provider-audit
```

The provider-audit demo is the main local golden path. It runs from the repo
root, uses the recorded provider fixture when no endpoint env var is set,
auto-approves the provider-use gate for reproducibility, and prints JSON with a
`run_id` plus the inspect working directory:

```powershell
cd examples\provider_audit
uv run agent-harness inspect run <run-id>
```

The Docker image is for local/demo reproducibility, not production deployment:

```powershell
docker build -t agent-harness:local .
docker run --rm agent-harness:local agent-harness demo provider-audit
```

Run the local checks with:

```powershell
uv run python -m pre_commit run --all-files
uv run pytest
uv run agent-harness eval
uv run agent-harness release readiness
```

The local pre-commit config runs Ruff lint/format checks, mypy, docs check,
compileall, a large file guard, and a private key guard.

For package-install verification:

```powershell
python -m pip install .
agent-harness doctor
agent-harness release package-check
```

The secondary V2 example remains the deterministic Python refactor task:

```powershell
agent-harness task validate examples/tasks/python_refactor.json
agent-harness run examples/tasks/python_refactor.json --dry-run
```

When the secondary demo is run from the repo root, it records
`.agent-harness/release/evidence/demo-python-refactor.json` for release
readiness.

The V7 bundled template-pack golden path is documented in
[`examples/template_pack_system/`](examples/template_pack_system/). It covers
`template list`, `template show python-lib`, `template validate python-lib`,
dry-run apply, preview-diff apply, clean apply, and release readiness.

The V8 skills-system scope is documented in
[`docs/skills-system.md`](docs/skills-system.md). Phase 0 establishes the local
workflow-guidance boundary and docs-check guard; skill CLI and runtime behavior
arrive in later V8 slices.

The optional LangGraph boundary proof is isolated behind the `langgraph` extra:

```powershell
uv sync --extra dev --extra langgraph
uv run agent-harness run examples/tasks/python_refactor.json --runtime langgraph --dry-run
```

## CLI Surface

```text
agent-harness init
agent-harness skill list
agent-harness skill show prd-plan-tdd-workflow
agent-harness skill validate write-a-prd
agent-harness skill render prd-plan-tdd-workflow
agent-harness skill pack validate ./local-skills
agent-harness template list
agent-harness template show python-lib
agent-harness template validate --all
agent-harness template apply python-lib --destination ./scratch-lib
agent-harness ingest docs docs
agent-harness task validate examples/tasks/python_refactor.json
agent-harness demo provider-audit
agent-harness run examples/tasks/python_refactor.json --dry-run
agent-harness run examples/tasks/python_refactor.json --runtime langgraph --dry-run
agent-harness approve <run-id> <action-id> --decision approve
agent-harness commit propose <run-id> --message "refactor: update approved files"
agent-harness benchmark list
agent-harness benchmark run local-samples swebench-python-refactor
agent-harness retrieval index build --index-id local-docs --paths docs --mode lexical
agent-harness retrieval index build --index-id dense-docs --paths docs --mode dense --dense-backend deterministic
agent-harness retrieval index build --index-id qdrant-docs --paths docs --mode dense --dense-backend qdrant-local
agent-harness retrieval index build --index-id server-docs --paths docs --mode dense --dense-backend qdrant-server
agent-harness retrieval query dense-docs --query "config loader policy" --mode dense --k 5
agent-harness retrieval query dense-docs --query "config loader policy" --mode hybrid --k 5
agent-harness retrieval scorecard scorecard.json --index-id dense-docs --k 5
agent-harness retrieval index list
agent-harness retrieval index show local-docs
agent-harness retrieval index delete local-docs
agent-harness inspect run <run-id>
agent-harness inspect context <run-id>
agent-harness inspect policy default
agent-harness eval
agent-harness release package-check
agent-harness release readiness
agent-harness export json <run-id>
agent-harness export markdown <run-id>
agent-harness export sarif <run-id>
agent-harness serve --host 127.0.0.1 --port 8765
agent-harness doctor
```

## Current Capabilities

- `agent-harness init` emits `config.v2` and `policy.v2`.
- Bundled examples use `task.v2`; bundled Python templates use `template.v2`.
- V1 config, task, policy, and template inputs remain readable through
  compatibility paths that do not widen policy or template capabilities.
- `policy.v2` owns provider-input rules, trust-zone rules, approval policy,
  scanner handling, template capability rules, and migration policy.
- The default retrieval backend is deterministic lexical retrieval. Local dense
  fixture behavior is opt-in through `retrieval_backend: qdrant`; missing
  Qdrant/FastEmbed dependencies fall back to lexical evidence.
- Lexical retrieval indexes can be built, listed, inspected, and deleted through
  `agent-harness retrieval index ...`; manifests record stable source and chunk
  evidence as `retrieval_index.v1`.
- Deterministic dense indexing and dense/hybrid query are available through the
  retrieval CLI for fixture and CI evidence. This backend uses local token-set
  scoring, requires no network or model download, records `retrieval_backend.v2`
  evidence, and is not a production embedding backend.
- With `agent-harness[retrieval]`, `--dense-backend qdrant-local` builds a
  persistent local Qdrant index under `.agent-harness/indexes/<index-id>/qdrant`
  using local FastEmbed embeddings. The manifest records the embedding model,
  model package version when available, collection name, storage path, and
  `remote_embeddings: false`.
- `--dense-backend qdrant-server` is optional loopback-only developer
  infrastructure. It accepts only `localhost`, `127.0.0.1`, and `::1` endpoints
  from `config.v2`, records endpoint/collection/model evidence, and reports
  unreachable loopback servers without enabling remote Qdrant.
- A `config.v2` retrieval `index_id` can route runtime context assembly through
  a built lexical, deterministic dense, qdrant-local, qdrant-server, or hybrid
  index. Accepted and rejected context manifest items retain lexical/dense
  provenance, per-method scores, backend/index evidence, and rejected-text
  redaction before provider input is built.
- `agent-harness retrieval scorecard` reads local labeled fixtures, compares
  lexical, dense, and hybrid query modes, computes Precision@k and Recall@k,
  records per-query hits, misses, and unexpected chunks without retrieved text,
  and writes `retrieval_scorecard.v1` artifacts under
  `.agent-harness/retrieval-scorecards/`. Release readiness reports at least
  one passing retrieval scorecard as retrieval evidence.
- [examples/retrieval_quality/](examples/retrieval_quality/) is the V5
  local-first retrieval demo. It includes runnable local config/policy files,
  public and internal sample documents, expected retrieval artifacts, a
  scorecard fixture, and commands for lexical build, qdrant-local hybrid build,
  hybrid query, scorecard comparison, and policy-filtered context assembly.
- `examples/provider_audit/` is the main V2 walkthrough. It uses recorded
  provider transport, a non-mock local endpoint trust zone, `network: false`,
  required provider-use approval, inspectable provider-input evidence, redacted
  provider-call artifacts, and JSON/Markdown/SARIF exports.
- Provider Core validates provider output as `provider_action_envelope.v1`
  before runtime action planning. Mock and recorded-fixture paths use the same
  boundary, and a narrow OpenAI-compatible live smoke path is available only
  with explicit env opt-in, configured credentials, network/trust-zone policy,
  and provider-use approval.

## Roadmap / Not Enabled By Init

Agent Harness does not claim enterprise readiness, general live provider
operation, production Qdrant server operation, hosted API/UI operation, MCP
workflows, multi-agent orchestration, external template catalogs, deployment
hardening, or compliance assurance. The v1.2.0 release established local-first
retrieval hardening on top of Provider Core: local retrieval index lifecycle
commands, hybrid retrieval, local FastEmbed/Qdrant evidence, retrieval
scorecards, and policy-filtered context manifests.

The retrieval quality demo is runnable under
[examples/retrieval_quality/](examples/retrieval_quality/). Cloud Qdrant,
remote embeddings, hosted embedding providers, and production Qdrant server
operation remain roadmap scope, not default behavior.

V6 adds a local operator surface:
[docs/operator-ui.md](docs/operator-ui.md),
[docs/prd-agent-harness-v6.md](docs/prd-agent-harness-v6.md), and
[plans/agent-harness-v6.md](plans/agent-harness-v6.md). It provides
`agent-harness serve`, a loopback-only local operator app, `/health`,
token-gated run list/detail APIs, context manifest inspection, policy
inspection, approval listing, approve/deny decisions through the existing
approval service, and a packaged static UI with no external assets. Release
readiness records operator evidence for app import, API smoke, token
enforcement, host rejection, approval binding, and static UI packaging. The
target remains a loopback-only inspection and approval UI over existing
artifacts, not hosted API/UI operation, enterprise authentication, MCP, or
multi-agent orchestration.

V7 is the local-first template-pack system:
[docs/template-pack-system.md](docs/template-pack-system.md),
[docs/prd-agent-harness-v7.md](docs/prd-agent-harness-v7.md), and
[plans/agent-harness-v7.md](plans/agent-harness-v7.md). The target keeps
template packs local and inspectable, adds `template.v2.toml` pack manifests,
dry-run and preview evidence, clean empty-target apply evidence, and
release-readiness gates. Remote template catalogs, marketplace behavior,
template signing, organization catalogs, cloud registries, lifecycle hooks,
script execution, enterprise governance, and conditional file inclusion remain
future-only scope.

V8 is planned as a local skills system:
[docs/skills-system.md](docs/skills-system.md),
[docs/prd-agent-harness-v8.md](docs/prd-agent-harness-v8.md), and
[plans/agent-harness-v8.md](plans/agent-harness-v8.md). The target keeps skills
local, inspectable, validated, and policy-mediated. Skills are workflow
guidance, not tools, templates, policy, approvals, provider profiles, or
executable code. Remote skill catalogs, marketplaces, signing, hosted skill
services, enterprise registries, organization-wide governance, centralized
governance, network installation, and automatic execution from skills remain
future-only scope.

## Documentation

- [Architecture](docs/architecture.md)
- [Local operator surface](docs/operator-ui.md)
- [Research foundations](docs/research-foundations.md)
- [Security model](docs/security-model.md)
- [Context packs and retrieval](docs/context-packs.md)
- [Evaluation strategy](docs/evaluations.md)
- [Provider Core](docs/provider-core.md)
- [Template catalog](docs/templates.md)
- [Template pack system](docs/template-pack-system.md)
- [Skills system](docs/skills-system.md)
- [Schema migration](docs/migration.md)
- [Release readiness](docs/release-readiness.md)
- [Conception alignment](docs/conception-alignment.md)
- [V4 Provider Core PRD](docs/prd-agent-harness-v4.md)
- [V5 Local-First Retrieval Hardening PRD](docs/prd-agent-harness-v5.md)
- [V6 Local Operator Surface PRD](docs/prd-agent-harness-v6.md)
- [V7 Template Pack System PRD](docs/prd-agent-harness-v7.md)
- [V8 Skills System PRD](docs/prd-agent-harness-v8.md)
- [V5 implementation plan](plans/agent-harness-v5.md)
- [V6 implementation plan](plans/agent-harness-v6.md)
- [V7 implementation plan](plans/agent-harness-v7.md)
- [V8 implementation plan](plans/agent-harness-v8.md)
- [Roadmap](docs/roadmap.md)

## License

Apache-2.0
