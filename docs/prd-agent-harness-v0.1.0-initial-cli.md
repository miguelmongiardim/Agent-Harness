# PRD: Agent Harness v0.1.0

## Problem Statement

Agent Harness v0.1.0 exists to recover a controlled local agent workflow from an
overgrown spike. The current repository has useful code, docs, and tests, but
the product boundary was not written down first. That creates three risks:

- architecture can grow faster than tested behavior
- public docs can claim capabilities that are only planned or partially spiked
- safety-critical boundaries such as policy, context, tools, approvals, and
  audit can be bypassed by convenience code

The primary users are developers and reviewers who want to inspect, test, and
demonstrate a local agent workflow for software-engineering tasks. They need a
small v0.1.0 that proves policy-gated execution, reproducible artifacts, and
approval-bound changes without claiming enterprise readiness.

## Solution

Agent Harness v0.1.0 is a local-first Python CLI that runs deterministic mock-agent
software-engineering tasks against fixture projects. A task run creates an
inspectable run directory with policy-mediated context, JSONL events,
checkpoints, approval records, summaries, and exports.

The solution deliberately rebuilds from public behavior using TDD. The current
spike is frozen as reference material. Code may be reused only after the
behavior it supports is covered by a public-interface test.

v0.1.0 focuses on these workflows:

- initialize a project scaffold and default policy
- validate task, policy, tool, context, approval, eval, and template models
- run a dry-run task and inspect its artifacts
- construct context only through policy-mediated sources
- execute tools only through policy-mediated calls
- pause risky patch actions for approval before mutation
- resume approved actions only when the approval binding still matches
- run evals that fail on policy bypass and emit scorecard artifacts
- export policy evidence as JSON, Markdown, and SARIF

v0.1.0 avoids production identity, network model providers, web APIs, web UIs,
multi-agent execution, broad template catalogs, and enterprise assurance claims.

## User Stories

1. As a developer, I want to initialize an Agent Harness project, so that I can
   run local agent workflow experiments from a known structure.
2. As a developer, I want to validate task and policy specs before a run, so
   that malformed or unsafe inputs fail before runtime.
3. As a developer, I want a dry-run task to create a run id and artifacts, so
   that I can inspect what the harness would do without mutating files.
4. As a reviewer, I want every context source and retrieval result to carry
   provenance and policy evidence, so that I can audit what reached the model
   boundary.
5. As a security reviewer, I want denied paths and sensitive data to be blocked
   from context and tools, so that untrusted or forbidden evidence cannot be
   used by the runtime.
6. As a developer, I want supported tools to execute through a policy boundary,
   so that reads, searches, test runs, patches, and git status cannot bypass
   the active permission ceiling.
7. As a reviewer, I want patch proposals to produce a diff and approval request
   without mutation, so that risky changes can be reviewed first.
8. As a reviewer, I want approved patch execution to be bound to the exact
   action, policy, checkpoint, arguments, and proposed effect, so that stale or
   tampered approvals cannot apply.
9. As a maintainer, I want deterministic mock-model behavior to depend on task
   specs, context, and observations, so that tests prove the runtime is not
   hard-coded to a task id.
10. As a maintainer, I want evals and exports to produce inspectable scorecards
    and SARIF, so that regressions and policy failures are visible in CI.

## Behavioral Requirements

1. A user can run `agent-harness init` and receive the expected local config,
   default policy, artifact directories, and starter docs without unsupported
   claims.
2. A user can list, show, and apply the `python-lib` template through the CLI,
   with file writes subject to policy.
3. A user can validate a valid task spec and receives concrete validation
   errors for invalid specs.
4. A dry-run task creates a run id, run directory, policy-mediated minimal
   context manifest, JSONL event log, checkpoint, summary, and inspectable
   artifacts.
5. `agent-harness inspect run <run-id>` displays the run summary and event
   evidence for a completed, paused, failed, or dry-run run.
6. `agent-harness inspect context <run-id>` displays the exact context manifest
   used by that run.
7. Policy profiles define permission ceilings; task specs and CLI options can
   narrow permissions but cannot widen them.
8. Denied paths, path traversal attempts, denied globs, and denied sensitivity
   classes cannot enter context construction.
9. Denied paths, path traversal attempts, denied globs, and disallowed tools
   cannot execute through tool calls.
10. Redaction rules are applied before content is written to model-facing
    context or tool observations.
11. `read_file`, `search_code`, `run_tests`, `patch_file`, and `git_status`
    execute only through policy-mediated public tool interfaces.
12. `patch_file` uses hash-checked full replacement with proposed content and
    a generated diff.
13. `patch_file` produces an approval request without mutating the target when
    approval is required.
14. An approved patch applies only if the approval binding matches run id,
    action id, tool name, arguments hash, policy profile, checkpoint hash, and
    proposed effect hash.
15. Changing task context or tool observations changes deterministic mock-model
    behavior when those inputs are relevant.
16. A fixed-seed run produces stable required artifacts and stable metadata
    where timestamps and run ids are fixed.
17. Evals fail on policy bypass, denied-context inclusion, or missing required
    artifacts.
18. Exports produce JSON, Markdown, and SARIF artifacts that reflect actual run
    evidence.

## Implementation Decisions

- **Public interface**: v0.1.0 is CLI-first. Required commands are `init`,
  `template list/show/apply`, `ingest docs`, `task validate`, `run`,
  `approve`, `inspect run/context/policy`, `eval`, `export sarif`, and
  `doctor`.
- **Repo structure**: the initial recovery structure is:
  `docs/`, `plans/`, `specs/`, `src/agent_harness/`, `tests/`, `.github/`,
  `mkdocs.yml`, `SECURITY.md`, `CONTRIBUTING.md`, and `CHANGELOG.md`.
  Restructure only when a vertical slice needs it.
- **Key models**: task, tool, policy, template, eval, approval, context
  manifest, run event, checkpoint, and summary are public boundary models.
- **Policy boundary**: policy is deny-by-default. Every context source,
  retrieval result, prompt-bound artifact, model output, tool call, approval,
  runtime action, and export passes through policy before use.
- **Context boundary**: external data, retrieved docs, prompts, model output,
  and tool output are untrusted evidence. They may inform the runtime but never
  grant permissions.
- **Tool boundary**: supported tools are narrow public capabilities, not a
  general shell. `run_tests` accepts allow-listed argv arrays only.
- **Approval boundary**: approval records are hash-bound to the exact proposed
  effect and re-checked before mutation.
- **Runtime boundary**: v0.1.0 uses a native plan-act-observe loop with a
  deterministic mock model. Framework adapters are roadmap items only.
- **Storage**: run artifacts live under `.agent-harness/runs/<run-id>`.
  JSONL events are append-only evidence. SQLite stores metadata needed for
  inspection and resumption.
- **Retrieval**: deterministic local retrieval is the normal path. Fake
  retrieval is for isolated unit tests. Qdrant/FastEmbed is optional smoke-path
  only in v0.1.0.
- **Docs**: public docs describe implemented behavior only. Roadmap material is
  separated from v0.1.0 behavior.

## Testing Decisions

- Use TDD one public behavior at a time: write one failing behavior test, make
  it pass minimally, then refactor while green.
- Tests target public behavior through CLI commands, public models, runtime
  entrypoints, tool interfaces, and exported artifacts.
- Unit tests cover schemas, policy rules, path traversal, redaction,
  sensitivity labels, hash binding, and persistence primitives.
- Integration tests cover CLI workflows, dry-run artifacts, retrieval fallback,
  approval pause/resume, patch behavior, inspection, and export.
- E2E tests cover a complete run lifecycle from task validation through
  inspection and export.
- Adversarial tests cover prompt injection in docs, forbidden access, denied
  context, policy bypass attempts, stale approvals, and patch tampering.
- v0.1.0 acceptance requires reproducible fixed-seed artifacts, no policy bypass,
  concrete output assertions, and docs that do not overclaim implemented
  behavior.

## Out of Scope

- Network model providers and provider credentials.
- Web API, web UI, approval dashboard, or hosted service mode.
- MCP, LangGraph, OpenTelemetry, and other adapters except as documented
  roadmap boundaries.
- Multi-agent execution.
- General shell execution.
- Production identity, tenant isolation, centralized secrets management,
  enterprise DLP, hardened sandboxing, or compliance assurance.
- Broad benchmark adapters such as SWE-bench or Terminal-Bench.
- v0.2.0/v0.3.0 roadmap features unless promoted by a later PRD and behavior test.

## Further Notes

- The current spike is useful reference material, not accepted v0.1.0
  implementation by default.
- The highest-risk v0.1.0 behaviors are policy mediation, denied-context exclusion,
  approval binding, dry-run non-mutation, and documentation accuracy.
- The first implementation step after this PRD is a walking skeleton test:
  CLI dry-run emits required artifacts and `inspect run` works.
