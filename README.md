# Agent Harness

Agent Harness is a local Python CLI for policy-gated agent workflow
experiments. It is built to make controlled software-engineering runs
inspectable: policy decisions, context selection, provider input, tool calls,
approvals, retrieval provenance, and release evidence all become local
artifacts.

The project is not enterprise-ready and does not claim production assurance.
It models enterprise concerns such as permission ceilings, approval binding,
audit trails, redaction, evidence packaging, and local review workflows without
claiming certification or hosted platform behavior.

## Current Status

The current package version is `1.9.1`. The base install is CLI-first and
local-first. Optional extras enable local retrieval dependencies, the loopback
operator app, the read-only MCP boundary, and the narrow LangGraph boundary
proof.

Useful docs:

- [Architecture](docs/architecture.md)
- [Security model](docs/security-model.md)
- [Release readiness](docs/release-readiness.md)
- [Roadmap](docs/roadmap.md)
- [Compliance evidence pack](docs/compliance-evidence-pack.md)

## What This Repo Proves

- Deterministic mock and recorded-fixture provider paths consume real task,
  context, policy, approval, and tool-observation evidence.
- Policy profiles are permission ceilings. Tasks and CLI flags can narrow
  authority, but they cannot widen it.
- Context, retrieval, provider input, tool execution, template writes,
  approvals, exports, governance, and evidence packaging pass through explicit
  boundaries.
- Retrieved content, issue text, model output, provider output, tool output,
  skill guidance, and external data are treated as untrusted evidence.
- Runs produce append-only JSONL events, context manifests, checkpoints,
  approval records, summaries, artifact indexes, and exportable JSON, Markdown,
  and SARIF.
- Local review surfaces exist for operator inspection, read-only MCP resources
  and prompts, governance evidence, benchmark comparisons, orchestration
  evidence, compliance evidence-pack review, and named local review profiles.

## Quick Start

```powershell
uv sync --extra dev
uv run agent-harness doctor
uv run agent-harness demo provider-audit
```

The provider-audit demo is the main reproducible walkthrough. It uses recorded
provider evidence when no live endpoint is configured, auto-approves the
provider-use gate for the demo, and prints a `run_id`.

Inspect the resulting run from the demo workspace:

```powershell
cd examples\provider_audit
uv run agent-harness inspect run <run-id>
cd ..\..
```

From the repo root, run the fast local validation profile:

```powershell
uv run pytest
uv run agent-harness docs check
uv run agent-harness eval
```

Run broader release-oriented checks when changing public behavior, release
evidence, demos, provider handling, retrieval, or end-to-end workflows:

```powershell
uv run python -m pre_commit run --all-files
uv run pytest -m slow
uv run agent-harness release package-check
uv run agent-harness release readiness
```

The local pre-commit config runs Ruff lint/format checks, mypy, docs check,
compileall, a large file guard, and a private key guard.

The Docker image is for local/demo reproducibility, not production deployment:

```powershell
docker build -t agent-harness:local .
docker run --rm agent-harness:local agent-harness demo provider-audit
```

## Implemented Locally

### Runtime And Policy

- `agent-harness init` emits `config.v2` and `policy.v2`.
- Bundled examples use `task.v2`; bundled Python templates use `template.v2`.
- v0.2.0 config, task, policy, and template inputs remain readable through
  non-widening compatibility paths.
- The native runtime is the primary execution path. The optional LangGraph path
  delegates through the native runtime and records adapter evidence.
- Provider Core validates provider output as `provider_action_envelope.v1`
  before runtime action planning.
- Live OpenAI-compatible smoke behavior is opt-in only and requires configured
  credentials, network/trust-zone policy, provider-use approval, and explicit
  environment opt-in.

### Retrieval And Context

- Agent Harness supports local retrieval without remote embeddings.
- Lexical indexes, deterministic dense indexes, hybrid query, qdrant-local, and
  loopback-only qdrant-server developer indexes are exposed through
  `agent-harness retrieval ...`.
- Context manifests retain accepted and rejected evidence, lexical/dense
  provenance, per-method scores, backend/index evidence, and redaction metadata.
- Retrieval scorecards compute local Precision@k and Recall@k evidence without
  copying retrieved text into release gates.
- The local-first retrieval golden path lives in
  [examples/retrieval_quality/](examples/retrieval_quality/).

### Templates And Skills

- Local template packs use `template.v2.toml`, deterministic parameter
  rendering, dry-run/preview evidence, clean apply evidence, and rollback on
  safe write failures.
- Bundled packs include `python-lib`, `cli-tool`, `fastapi-service`,
  `provider-audit`, and `retrieval-quality`.
- Skills are local Markdown workflow guidance, not executable tools. They can
  be listed, shown, rendered, validated, resolved for tasks, and recorded in
  `skill_manifest.v1` evidence.
- The template-pack golden path lives in
  [examples/template_pack_system/](examples/template_pack_system/).
- The skills workflow golden path lives in
  [examples/skills_workflow/](examples/skills_workflow/).

### Operator, MCP, Orchestration, And Benchmarks

- `agent-harness serve` starts a loopback-only local operator app for inspecting
  existing run evidence and making existing approval decisions through the same
  approval service as the CLI.
- The optional MCP boundary is local and read-only. It exposes selected
  resources and review prompts over existing evidence and records metadata-only
  access logs.
- Local orchestration supports sequential, policy-mediated child `task.v2`
  dry-runs with explicit `policy.v2.orchestration` enablement, role ceilings,
  supervisor plan approval, handoff evidence, child pause/failure propagation,
  approval-bound resume, and safe JSON export.
- Benchmark comparison runs a single-agent baseline first, then deterministic
  sequential orchestration modes, and records comparison metrics without
  changing policy defaults or generated role lists.
- The MCP golden path lives in [examples/mcp_boundary/](examples/mcp_boundary/).
- The orchestration golden path lives in
  [examples/orchestration_workflow/](examples/orchestration_workflow/).

### Governance And Evidence Pack

The v1.8.0 local governance evidence surface includes
`agent-harness governance summary`, `agent-harness governance check`,
`agent-harness governance report --format markdown`, JSON reports, and
`agent-harness governance export --output .agent-harness/governance/`.

Governance commands emit local `governance_summary.v1`,
`governance_check.v1`, `governance_report.v1`, `governance_index.v1`, and
`governance_findings.v1` evidence. They read local config, policy, run
summaries, docs-check evidence, provider artifact risk, and safe evidence refs.

The v1.9.0 Compliance Evidence Pack is implemented as a local review packaging boundary.
It depends on completed v1.8.0 governance exports and provides:

- `agent-harness evidence pack`
- `agent-harness evidence check`
- `agent-harness evidence index`
- canonical `evidence_pack.v1`, `evidence_manifest.v1`, `evidence_index.v1`,
  `evidence_findings.v1`, `control_mapping.v1`, and checksum files
- review-only Markdown output and opt-in archives
- token-protected read-only operator API/UI views for existing pack artifacts
- a non-mutating release-readiness gate that validates existing pack files

The v1.9.0 PRD and implementation plan remain the durable design records:

- [v1.9.0 Compliance Evidence Pack PRD](docs/prd-agent-harness-v1.9.0-compliance-evidence-pack.md)
- [v1.9.0 compliance evidence pack plan](plans/agent-harness-v1.9.0-compliance-evidence-pack.md)

The evidence pack supports review and audit preparation. It does not certify
compliance with any legal, regulatory, security, or organizational framework.

### Reviewer Ergonomics

The v2.0.0 Reviewer Ergonomics release adds an additive local review command
family over existing checks and evidence:

- `agent-harness review profiles`
- `agent-harness review status`
- `agent-harness review run`
- `agent-harness review artifacts`

Built-in `quick`, `standard`, and `release` profiles make the expected command
sets inspectable and runnable without changing policy, approval, provider, eval,
template, evidence-pack, or release-readiness ownership. Review runs continue
through required-command failures, write `review_run.v1` evidence under
`.agent-harness/review/`, and redact unsafe output summaries. Artifact review
writes `artifact_inventory.v1` and a dry-run-only `artifact_cleanup_plan.v1`;
it never deletes files.

The v2.0.0 PRD and implementation plan remain the durable design records:

- [v2.0.0 Reviewer Ergonomics PRD](docs/prd-agent-harness-v2.0.0-reviewer-ergonomics.md)
- [v2.0.0 reviewer ergonomics plan](plans/agent-harness-v2.0.0-reviewer-ergonomics.md)

## Common Commands

```text
agent-harness init
agent-harness doctor
agent-harness docs check
agent-harness demo provider-audit
agent-harness task validate examples/tasks/python_refactor.json
agent-harness run examples/tasks/python_refactor.json --dry-run
agent-harness approve <run-id> <action-id> --decision approve
agent-harness commit propose <run-id> --message "refactor: update approved files"
agent-harness inspect run <run-id>
agent-harness inspect context <run-id>
agent-harness inspect policy default
agent-harness export json <run-id>
agent-harness export markdown <run-id>
agent-harness export sarif <run-id>

agent-harness template list
agent-harness template show python-lib
agent-harness template validate --all
agent-harness template apply python-lib --destination ./scratch-lib --dry-run

agent-harness skill list
agent-harness skill show prd-plan-tdd-workflow
agent-harness skill validate write-a-prd
agent-harness skill render prd-plan-tdd-workflow
agent-harness skill resolve --task examples/skills_workflow/task.yaml
agent-harness skill pack validate ./local-skills

agent-harness retrieval index build --index-id local-docs --paths docs --mode lexical
agent-harness retrieval index build --index-id dense-docs --paths docs --mode dense --dense-backend deterministic
agent-harness retrieval query dense-docs --query "config loader policy" --mode hybrid --k 5
agent-harness retrieval scorecard examples/retrieval_quality/scorecard.yaml --index-id dense-docs --k 5
agent-harness retrieval index list
agent-harness retrieval index show local-docs
agent-harness retrieval index delete local-docs

agent-harness serve --host 127.0.0.1 --port 8765
agent-harness mcp resources list
agent-harness mcp resources read agent-harness://runs/<run-id>/summary
agent-harness mcp prompts list
agent-harness mcp prompts get agent-harness-run-review

agent-harness orchestration run examples/orchestration_workflow/orchestration.json --dry-run
agent-harness orchestration inspect <orchestration-id>
agent-harness orchestration export <orchestration-id>
agent-harness orchestration approve <orchestration-id> <action-id> --decision approve
agent-harness orchestration resume <orchestration-id>

agent-harness benchmark list
agent-harness benchmark run local-samples terminal-readonly-inspect
agent-harness benchmark compare local-samples

agent-harness governance summary
agent-harness governance check
agent-harness governance report --format markdown
agent-harness governance report --format json
agent-harness governance export --output .agent-harness/governance/

agent-harness evidence pack --format json
agent-harness evidence check
agent-harness evidence index

agent-harness review profiles
agent-harness review status --profile quick
agent-harness review run --profile quick
agent-harness review artifacts

agent-harness eval
agent-harness release package-check
agent-harness release readiness
```

## Roadmap / Not Enabled By Init

- Compliance readiness and formal certification remain future-only.
- The evidence pack does not certify compliance, assert framework conformance,
  or replace legal, regulatory, security, or organizational review.
- Hosted APIs, remote web UI operation, multi-user authentication, cloud
  deployment, and production web-service operation are outside the current
  local operator boundary.
- Remote embeddings, hosted embedding providers, cloud Qdrant, remote vector
  databases, and production Qdrant operation remain outside the current
  retrieval boundary.
- MCP tools, write-capable MCP, HTTP MCP, hosted MCP services, remote gateways,
  and MCP runtime adapter behavior remain future-only.
- Parallel multi-agent orchestration, nested orchestration, hosted
  orchestration, and MCP execution for orchestration remain future-only.
- Remote template catalogs, template marketplaces, template signing, remote
  skill catalogs, skill marketplaces, skill signing, and network skill
  installation remain future-only.
- Role-count expansion requires comparative outcome evidence before any
  recommendation or policy/default promotion.
- v2.0.0 review artifacts do not provide hosted operation, MCP tool execution,
  live provider expansion, production retrieval, compliance certification,
  destructive cleanup, or release-readiness replacement.

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
- [Skill pack system](docs/skills-system.md)
- [MCP boundary](docs/mcp-boundary.md)
- [Schema migration](docs/migration.md)
- [Release readiness](docs/release-readiness.md)
- [Conception alignment](docs/conception-alignment.md)
- [v1.8.0 Local Governance Console PRD](docs/prd-agent-harness-v1.8.0-local-governance-console.md)
- [v1.8.0 local governance console plan](plans/agent-harness-v1.8.0-local-governance-console.md)
- [v1.9.0 Compliance Evidence Pack PRD](docs/prd-agent-harness-v1.9.0-compliance-evidence-pack.md)
- [v1.9.0 compliance evidence pack plan](plans/agent-harness-v1.9.0-compliance-evidence-pack.md)
- [v2.0.0 Reviewer Ergonomics PRD](docs/prd-agent-harness-v2.0.0-reviewer-ergonomics.md)
- [v2.0.0 reviewer ergonomics plan](plans/agent-harness-v2.0.0-reviewer-ergonomics.md)
- [Roadmap](docs/roadmap.md)
- [Changelog](CHANGELOG.md)

## License

Apache-2.0
