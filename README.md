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
uv run pytest -m slow
uv run agent-harness eval
uv run agent-harness release readiness
```

`uv run pytest` uses the fast default profile and skips tests marked `slow`.
Run `uv run pytest -m slow` before release work or when changing provider,
retrieval, release-evidence, or end-to-end demo behavior.

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
[`docs/skills-system.md`](docs/skills-system.md). Current slices provide
bundled and configured local skill discovery, validation, inspection, rendered
Markdown review, read-only skill-pack validation, task-requested skill
resolution, template-recommended skill evidence, and policy-gated skill
guidance in run context manifests. Runs that use selected skills now emit
`skill_manifest.json`, link it from summaries and artifact indexes, expose it
through `inspect run`, and allow eval specs to assert expected skill ids. The
V8 golden path lives in
[`examples/skills_workflow/`](examples/skills_workflow/) and release readiness
verifies bundled skill validation, resolution, manifest evidence, inspect
output, docs, and the demo.

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
agent-harness skill resolve --task <task.yaml>
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
agent-harness orchestration run orchestration.json --dry-run
agent-harness orchestration inspect <orchestration-id>
agent-harness orchestration export <orchestration-id>
agent-harness orchestration approve <orchestration-id> <action-id> --decision approve
agent-harness orchestration resume <orchestration-id>
agent-harness approve <run-id> <action-id> --decision approve
agent-harness commit propose <run-id> --message "refactor: update approved files"
agent-harness benchmark list
agent-harness benchmark run local-samples swebench-python-refactor
agent-harness benchmark compare local-samples terminal-readonly-inspect
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
agent-harness governance summary
agent-harness governance check
agent-harness governance report --format markdown
agent-harness governance report --format json
agent-harness governance export --output .agent-harness/governance/
agent-harness evidence pack --format json
agent-harness evidence check
agent-harness evidence index
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

V8 is the local skills system:
[docs/skills-system.md](docs/skills-system.md),
[docs/prd-agent-harness-v8.md](docs/prd-agent-harness-v8.md), and
[plans/agent-harness-v8.md](plans/agent-harness-v8.md). The implementation keeps
skills local, inspectable, validated, and policy-mediated. Skills are workflow
guidance, not tools, templates, policy, approvals, provider profiles, or
executable code. Remote skill catalogs, marketplaces, signing, hosted skill
services, enterprise registries, organization-wide governance, centralized
governance, network installation, and automatic execution from skills remain
future-only scope. The V8 path includes the skills workflow demo and
release-readiness gates for local skill evidence.

V9 is the MCP Boundary track:
[docs/mcp-boundary.md](docs/mcp-boundary.md),
[docs/prd-agent-harness-v9.md](docs/prd-agent-harness-v9.md), and
[plans/agent-harness-v9.md](plans/agent-harness-v9.md). The implementation is a
local, optional, read-only MCP boundary over existing Agent Harness evidence
under `agent_harness.mcp`, not a runtime adapter. It keeps MCP tools, write
actions, approval mutation, provider execution, run creation, arbitrary
filesystem resources, HTTP transport, hosted MCP service, remote gateways, and
enterprise registries future-only.

V11 planning is captured in
[`docs/prd-agent-harness-v11.md`](docs/prd-agent-harness-v11.md) and
[`plans/agent-harness-v11.md`](plans/agent-harness-v11.md). The current V11
implementation supports local, sequential, policy-mediated
`agent-harness orchestration run <spec> --dry-run` workflows with explicit
`policy.v2.orchestration` enablement, role ceilings, supervisor plan approvals,
normal child `task.v2` run artifacts, generated dependency handoffs, child
provider gates, child pause/failure propagation, approval-bound resume,
`orchestration export`, and read-only MCP resources for orchestration summary,
manifest, events, children, and handoffs. The V11 golden path lives in
`examples/orchestration_workflow/`, and release readiness verifies the
orchestration demo, policy gates, artifacts, inspect/export, MCP resource
reads, and MCP access-log evidence. Operator UI support and enterprise
governance remain future scope. Parallel multi-agent orchestration remains
future-only. Nested orchestration remains future-only. MCP execution for
multi-agent orchestration remains future-only. V11 does not support hosted
APIs.

The V11 multi-agent complexity benchmark is planned separately in
[`docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md`](docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md)
and
[`plans/agent-harness-v11-multi-agent-complexity-benchmark.md`](plans/agent-harness-v11-multi-agent-complexity-benchmark.md).
The implemented comparison path supports
`agent-harness benchmark compare local-samples terminal-readonly-inspect` for a
single case and `agent-harness benchmark compare local-samples` for the bundled
pack. It runs a single-agent baseline first, then sequential planner ->
implementer and planner -> implementer -> reviewer orchestration dry runs. It
also records planner -> implementer -> reviewer -> tester mode as skipped when
the case lacks executable `test_commands`, and runs that tester mode for
test-enabled bundled cases. Comparison artifacts use
`benchmark_comparison_result.v1` and `benchmark_comparison_suite.v1` under
`.agent-harness/benchmarks/comparisons/`, link per-case evidence, preserve
per-mode statuses, and include evidence-derived metrics
for task success, test evidence, policy violations, approval state, child/tool
and handoff counts, handoff size, coordination overhead, artifact completeness,
failure attribution, handoff usefulness, conservative role recommendations,
and explicit unavailable token/runtime/cost values. Role recommendations include
reason codes and supporting metric names, and they do not alter policy defaults
or generated orchestration role lists. `agent-harness eval` includes a local
comparison eval that enforces inspectable baseline evidence. Broader-pack
allowlists and automatic default-role promotion remain future scope.
Role-count expansion requires comparative outcome evidence before
recommendation or promotion.

V12 local governance evidence surface:
[docs/prd-agent-harness-v12-local-governance-console.md](docs/prd-agent-harness-v12-local-governance-console.md)
and
[plans/agent-harness-v12-local-governance-console.md](plans/agent-harness-v12-local-governance-console.md).
Phase 3 implements `agent-harness governance summary`,
`agent-harness governance check`, `agent-harness governance report`, and
`agent-harness governance export` as local, read-only views over config,
policy, run-summary artifacts, docs-check evidence, provider payload artifact
risk, and safe governance export metadata. The commands emit
`governance_summary.v1`, `governance_check.v1`, `governance_report.v1`,
`governance_index.v1`, and
`governance_findings.v1` data, reject unsafe artifact references, report raw
provider payload artifacts without exposing their contents, and write exports
only when explicitly requested. Operator API/UI and release-readiness gates
remain future-only.
Compliance readiness and formal certification remain future-only.

V1.9 Compliance Evidence Pack planning is captured in
[docs/compliance-evidence-pack.md](docs/compliance-evidence-pack.md),
[docs/prd-agent-harness-v1.9-compliance-evidence-pack.md](docs/prd-agent-harness-v1.9-compliance-evidence-pack.md),
and
[plans/agent-harness-v1.9-compliance-evidence-pack.md](plans/agent-harness-v1.9-compliance-evidence-pack.md).
The pack depends on completed V12 governance exports and packages existing
evidence for review. Phase 2 adds `agent-harness evidence pack`, `check`, and
`index` command discovery, prerequisite validation for missing V12 governance
exports, and `evidence pack --format json` generation of canonical
`evidence_pack.v1`, `evidence_manifest.v1`, `evidence_index.v1`,
`evidence_findings.v1`, and checksum files. Markdown presentation, archive
creation, control mapping, operator routes, UI views, and release-readiness
gates remain later-phase work. The evidence pack does not certify compliance
with any legal, regulatory, security, or organizational framework.

## Documentation

- [Architecture](docs/architecture.md)
- [Local operator surface](docs/operator-ui.md)
- [Research foundations](docs/research-foundations.md)
- [Security model](docs/security-model.md)
- [Context packs and retrieval](docs/context-packs.md)
- [Evaluation strategy](docs/evaluations.md)
- [Provider Core](docs/provider-core.md)
- [Compliance evidence pack](docs/compliance-evidence-pack.md)
- [Template catalog](docs/templates.md)
- [Template pack system](docs/template-pack-system.md)
- [Skills system](docs/skills-system.md)
- [MCP boundary](docs/mcp-boundary.md)
- [Schema migration](docs/migration.md)
- [Release readiness](docs/release-readiness.md)
- [Conception alignment](docs/conception-alignment.md)
- [V4 Provider Core PRD](docs/prd-agent-harness-v4.md)
- [V5 Local-First Retrieval Hardening PRD](docs/prd-agent-harness-v5.md)
- [V6 Local Operator Surface PRD](docs/prd-agent-harness-v6.md)
- [V7 Template Pack System PRD](docs/prd-agent-harness-v7.md)
- [V8 Skills System PRD](docs/prd-agent-harness-v8.md)
- [V9 MCP Boundary PRD](docs/prd-agent-harness-v9.md)
- [V11 Policy-Mediated Multi-Agent Orchestration PRD](docs/prd-agent-harness-v11.md)
- [V11 Multi-Agent Complexity Benchmark PRD](docs/prd-agent-harness-v11-multi-agent-complexity-benchmark.md)
- [V12 Local Governance Console PRD](docs/prd-agent-harness-v12-local-governance-console.md)
- [V1.9 Compliance Evidence Pack PRD](docs/prd-agent-harness-v1.9-compliance-evidence-pack.md)
- [V5 implementation plan](plans/agent-harness-v5.md)
- [V6 implementation plan](plans/agent-harness-v6.md)
- [V7 implementation plan](plans/agent-harness-v7.md)
- [V8 implementation plan](plans/agent-harness-v8.md)
- [V9 implementation plan](plans/agent-harness-v9.md)
- [V11 implementation plan](plans/agent-harness-v11.md)
- [V11 multi-agent complexity benchmark plan](plans/agent-harness-v11-multi-agent-complexity-benchmark.md)
- [V12 local governance console plan](plans/agent-harness-v12-local-governance-console.md)
- [V1.9 compliance evidence pack plan](plans/agent-harness-v1.9-compliance-evidence-pack.md)
- [Roadmap](docs/roadmap.md)

## License

Apache-2.0
