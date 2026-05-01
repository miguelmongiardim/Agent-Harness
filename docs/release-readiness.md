# Release Readiness

## Current Capabilities

`agent-harness release readiness` writes a local
`release_readiness.v1` report under `.agent-harness/release/`.

The command defaults to `[project].version` from `pyproject.toml`. Release
managers can still bind the report to an explicit version and CI run:

```powershell
agent-harness release readiness --version 1.7.1 --ci-run-id <run-id>
```

When GitHub CLI is authenticated, the command attempts to discover the latest
`CI` workflow run for the release target commit.

Package and clean-install evidence is generated with:

```powershell
agent-harness release package-check
```

The local development install path remains:

```powershell
uv sync --extra dev
uv run agent-harness doctor
```

Contributor hygiene is available through the local pre-commit config:

```powershell
python -m pre_commit run --all-files
```

The hooks run Ruff lint/format checks, mypy, docs check, compileall, a large
file guard, and a private key guard. They use local hooks so normal contributor
checks do not depend on optional advisory scanner installs.

CI keeps advisory evidence visible with optional Gitleaks and CycloneDX/SBOM
outputs under `.agent-harness/advisories/`. Those reports are useful review
inputs, but advisory tooling is optional and must not block required CI when the
tools are absent.

The package install path is:

```powershell
python -m pip install .
agent-harness doctor
```

The Docker path is local/demo reproducibility packaging, not production
deployment:

```powershell
docker build -t agent-harness:local .
docker run --rm agent-harness:local agent-harness demo provider-audit
```

CI runs the same Docker build and provider-audit demo command in a dedicated
Docker demo job.

Required demo evidence is generated with:

```powershell
agent-harness demo provider-audit
agent-harness run examples/tasks/python_refactor.json --dry-run
```

Those commands record `.agent-harness/release/evidence/demo-provider-audit.json`
and `.agent-harness/release/evidence/demo-python-refactor.json`. The
provider-audit demo remains the main reproducible walkthrough; Python refactor
remains the secondary dry-run demo.

Retrieval scorecard evidence is generated with:

```powershell
agent-harness retrieval index build --index-id demo-retrieval --paths examples/retrieval_quality/docs --mode hybrid --dense-backend deterministic --overwrite
agent-harness retrieval scorecard examples/retrieval_quality/scorecard.yaml --index-id demo-retrieval --k 5
```

These commands record a passing `retrieval_scorecard.v1` artifact under
`.agent-harness/retrieval-scorecards/`. Release readiness reports this as the
retrieval scorecard gate and leaves the report pending when no passing
scorecard exists.

Release readiness also verifies that `examples/retrieval_quality/` includes
the runnable demo files and scans executable configs such as
`agent-harness.yaml`, example `agent-harness.yaml` files, and example
`config.v2.yaml` files for remote retrieval defaults. A report remains pending
when those configs enable remote embeddings, hosted embedding providers,
API-key-backed Qdrant, cloud Qdrant, HTTPS Qdrant, or non-loopback Qdrant
endpoints.

The report represents:

- package build evidence
- clean-install evidence
- installed console-script evidence
- required demo evidence
- docs gate status
- schema compatibility documentation presence
- roadmap-claim docs status
- bundled template validation evidence
- bundled template-pack acceptance evidence for validation, dry-run,
  clean apply, generated example schema checks, docs presence, and
  `template_application.v1` evidence
- local-only template catalog configuration evidence
- retrieval scorecard evidence
- retrieval demo and local-first config evidence
- operator app factory, API smoke, token requirement, loopback host rejection,
  approval binding, and static UI packaging evidence
- V8 skill validation, registry command, workflow demo, manifest, inspect, and
  skills docs evidence
- V9 MCP boundary demo, optional extra, CI install, CLI resource and prompt,
  denial, access log, and stdio resources/prompts-only evidence
- V11 orchestration workflow demo, policy, artifact, inspect/export, read-only
  MCP resource, and metadata-only MCP access-log evidence
- release artifact presence
- local check commands
- remote CI run evidence for the target commit
- remote CI status fields for Python 3.11 and Python 3.12
- Python 3.13 allowed-failure status field
- advisory Gitleaks and CycloneDX report references
- changelog entry presence
- release tag target commit evidence
- actionable diagnostics for missing or failed evidence

The command is evidence collection, not release automation. A report is `ready`
only when required package, install, console script, demo, docs, changelog,
template, retrieval scorecard, retrieval demo/config, operator, skills, MCP,
orchestration, artifact, tag, and remote CI evidence is present and passing.

For V7 template packs, release readiness refreshes `template validate --all`
evidence, then validates every bundled pack through a temporary release
workspace. Each bundled pack must validate, produce dry-run evidence without
mutating the target, clean-apply to a temporary target, generate valid
`config.v2`, `task.v2`, `policy.v2`, and `eval.v1` examples, include README or
docs content, and record completed `template_application.v1` evidence. The
report also scans executable template config defaults and stays pending when a
remote catalog, marketplace URL, cloud registry, or registry URL is configured
as a default.

## V8 Skill Gates

For V8 skills, release readiness validates all required bundled skills:
`write-a-prd`, `prd-to-plan`, `tdd`, and `prd-plan-tdd-workflow`. It verifies
skill list/show/validate behavior, resolves
`examples/skills_workflow/task.yaml`, runs that task as a dry run, checks
`context_manifest.json` skill provenance, checks `skill_manifest.v1` evidence,
and verifies `inspect run` includes the skill manifest.

Release readiness also verifies `docs/skills-system.md` exists, docs check is
passing, and deferred skill distribution and governance features remain outside
implemented scope.

## V9 MCP Gates

For V9, release readiness verifies the local read-only MCP Boundary. The
golden-path example lives at `examples/mcp_boundary/` and documents the
resource, prompt, denial, access-log, and stdio checks.

The report records:

- `mcp.demo` for the `examples/mcp_boundary/` README and expected JSON outputs.
- `mcp.extra_install` for the declared `agent-harness[mcp]` extra and SDK import.
- `mcp.ci_install` for CI installing the MCP extra before release readiness.
- `mcp.cli_commands` for the public `agent-harness mcp` command group.
- `mcp.resource_listing` for `mcp resources list --json`.
- `mcp.resource_reads` for summary and context resource envelopes.
- `mcp.prompt_commands` for prompt list/get behavior.
- `mcp.denied_resource` for safe denial of arbitrary file URI reads.
- `mcp.access_log` for metadata-only `mcp_access_log.v1` records.
- `mcp.stdio_protocol` for resources/prompts advertised with no tools
  capability.

MCP tools, write-capable MCP, Streamable HTTP MCP, hosted MCP service, remote
gateways, enterprise registries, and MCP runtime adapter behavior remain outside
implemented scope.

## V11 Orchestration Gates

For V11, release readiness verifies the local sequential orchestration
workflow. The golden-path example lives at `examples/orchestration_workflow/`
and documents the dry-run, inspect, export, read-only MCP resource, and
release-readiness commands.

The report records:

- `orchestration.demo` for the `examples/orchestration_workflow/` README,
  local config, policy, orchestration spec, and Python fixture.
- `orchestration.policy_gates` for explicit `policy.v2.orchestration`
  enablement, sequential execution, disabled nested orchestration, role
  ceilings, and no denied child authority.
- `orchestration.artifact_checks` for aggregate summary, events, manifest,
  artifact index, child task/run artifacts, and generated handoff artifacts.
- `orchestration.inspect_export` for public inspect/export commands and
  exports that avoid raw provider payloads and absolute workspace paths.
- `orchestration.mcp_resource_reads` for read-only MCP orchestration summary
  and handoff resource envelopes.
- `orchestration.mcp_access_log` for metadata-only MCP access records tied to
  the orchestration id.

V11 does not support hosted APIs. It does not support parallel multi-agent
orchestration, nested orchestration, or MCP execution for multi-agent
orchestration. Operator UI support and enterprise governance remain
future-only.

## Future Evidence Pack Gate

The V1.9 Compliance Evidence Pack is planned as a later release-readiness input.
Phase 3 evidence commands validate missing V12 governance export prerequisites,
generate canonical JSON packs with `agent-harness evidence pack --format json`,
and omit unsafe governance-index artifact references with evidence findings.
Release readiness does not generate evidence packs. It may only validate an
existing pack once the release-readiness evidence gate is implemented.

Until that phase exists, release readiness must not claim evidence-pack gates,
control mapping, certification, auditor approval, or formal framework
readiness.

## Release Checklist

Before tagging the current release:

1. Run `uv sync --extra dev`.
2. Run `python -m pre_commit run --all-files`.
3. Run `python -m pytest -q` for the fast default profile.
4. Run `python -m pytest -q -m slow` for slow provider, retrieval,
   release-evidence, and golden-path tests.
5. Run `agent-harness release package-check`.
6. Run `agent-harness demo provider-audit`.
7. Run `agent-harness run examples/tasks/python_refactor.json --dry-run`.
8. Run `agent-harness template validate --all`.
9. Run the template-pack golden path in `examples/template_pack_system/`.
10. Run the local retrieval index build and scorecard commands above.
11. Run `uv sync --extra operator`.
12. Run `uv run agent-harness demo provider-audit`.
13. Run `uv run agent-harness serve --host 127.0.0.1 --port 8765` and verify
    the local UI with the generated token.
14. Run the skills workflow golden path in `examples/skills_workflow/`.
15. Run `uv sync --extra mcp`.
16. Run the MCP boundary golden path in `examples/mcp_boundary/`.
17. Run the orchestration workflow golden path in
    `examples/orchestration_workflow/`.
18. Run `agent-harness eval`.
19. Run `agent-harness release readiness --version 1.7.1`.
20. Confirm CI passes for the release commit.

## Tag Process

Create the release tag only after the release commit is pushed and required CI
has passed for that exact commit:

```powershell
git tag -a v1.7.1 -m "v1.7.1"
git push origin v1.7.1
agent-harness release readiness --version 1.7.1 --ci-run-id <run-id>
```

The readiness report binds the tag target commit to the recorded GitHub Actions
run. A report is not ready when the run is missing, failed, or points at a
different commit.

## Artifact Verification

`agent-harness release package-check` records wheel and source distribution
hashes in `.agent-harness/release/package-check.json` and supporting evidence
files under `.agent-harness/release/evidence/`. Reviewers should verify that:

- `dist/agent_harness-1.7.1-*.whl` exists.
- `dist/agent_harness-1.7.1.tar.gz` exists.
- package-check evidence reports `status: passed`.
- clean-install evidence reports `status: passed`.
- console-script evidence reports `status: passed`.
- the final readiness report is generated for `version: 1.7.1`.

## Roadmap

Automated release publishing, production deployment artifacts, and compliance
attestation are outside the current release workflow.

For the V6 local operator surface, release readiness now records operator
evidence under `operator.app_factory`, `operator.api_smoke`,
`operator.token_required`, `operator.host_rejection`,
`operator.approval_binding`, and `operator.static_ui`. Those gates verify the
optional operator import path, local health route, token enforcement,
loopback-only serve behavior, approval binding protection, packaged static UI
metadata, and absence of external UI references. Hosted API behavior, remote web
UI operation, enterprise control plane evidence, and compliance attestation
remain outside the V6 release readiness target.
