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

The optional LangGraph boundary proof is isolated behind the `langgraph` extra:

```powershell
uv sync --extra dev --extra langgraph
uv run agent-harness run examples/tasks/python_refactor.json --runtime langgraph --dry-run
```

## CLI Surface

```text
agent-harness init
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
operation, production Qdrant server operation, a web API/UI, MCP workflows,
multi-agent orchestration, external template catalogs, deployment hardening, or
compliance assurance. The v1.1.0 release establishes Provider Core: strict
provider action envelopes, profile validation, opt-in OpenAI-compatible live
smoke, provider-call evidence, redacted prompt/response artifacts, and
deterministic provider-core evals.

The V5 plan targets local-first retrieval hardening for v1.2.0. The planned
retrieval quality demo is tracked under
[examples/retrieval_quality/](examples/retrieval_quality/), with the runnable
golden path landing after the retrieval CLI, local index, and scorecard slices
are implemented.

## Documentation

- [Architecture](docs/architecture.md)
- [Research foundations](docs/research-foundations.md)
- [Security model](docs/security-model.md)
- [Context packs and retrieval](docs/context-packs.md)
- [Evaluation strategy](docs/evaluations.md)
- [Provider Core](docs/provider-core.md)
- [Template catalog](docs/templates.md)
- [Schema migration](docs/migration.md)
- [Release readiness](docs/release-readiness.md)
- [Conception alignment](docs/conception-alignment.md)
- [V4 Provider Core PRD](docs/prd-agent-harness-v4.md)
- [V5 Local-First Retrieval Hardening PRD](docs/prd-agent-harness-v5.md)
- [V5 implementation plan](plans/agent-harness-v5.md)
- [Roadmap](docs/roadmap.md)

## License

Apache-2.0
