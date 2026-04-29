# PRD: Agent Harness V9 MCP Boundary

V9 targets `v1.6.0`.

## Problem Statement

Agent Harness already produces inspectable local evidence: run summaries,
context manifests, approvals, provider-call evidence, eval results, retrieval
scorecards, template metadata, and skill manifests. Reviewers and MCP-compatible
clients cannot consume that evidence through a standard MCP boundary today.

Without a narrow MCP surface, users either inspect artifacts through the CLI and
operator UI only, or they build ad hoc local readers that risk bypassing policy,
redaction, approval, and audit boundaries. Full MCP automation would be too broad
for the next release because MCP tools, write operations, HTTP transport,
provider calls, approvals, and run execution would expand Agent Harness into a
new execution surface before the read-only evidence boundary is proven.

The affected actors are:

- reviewers who need structured, policy-filtered access to run evidence
- MCP-compatible clients that need standardized resources and prompts
- release reviewers who need proof that MCP does not expose tools or mutation
- security reviewers who need denial, redaction, and access evidence

## Solution

V9 adds a local, optional, read-only MCP boundary under `agent_harness.mcp`.
It exposes selected Agent Harness evidence through MCP resources and review
prompts while preserving policy, redaction, approval, and audit boundaries.

The V9 MCP surface is not a runtime adapter. The existing
`agent_harness.runtimes.mcp_adapter` may remain unsupported because V9 does not
run tasks through MCP. MCP is an interoperability boundary over existing local
evidence.

The user-facing workflow is:

1. Install the optional MCP extra with `uv sync --extra mcp` or
   `pip install "agent-harness[mcp]"`.
2. Run provider-audit or another local workflow that creates run artifacts.
3. Use `agent-harness mcp resources list --json` to discover allowlisted
   resources.
4. Use `agent-harness mcp resources read <uri> --json` to inspect a safe
   resource envelope.
5. Use `agent-harness mcp prompts list --json` and
   `agent-harness mcp prompts get <name> --json` to retrieve deterministic
   review prompts.
6. Start `agent-harness mcp serve` only when the optional SDK is installed.
7. Verify the stdio MCP server advertises resources and prompts, but no tools.
8. Inspect `.agent-harness/mcp/access-log.jsonl` as append-only MCP access
   evidence.

The solution deliberately avoids MCP tools, write-capable actions, approval
mutation, provider execution, run creation, arbitrary file reads, HTTP transport,
hosted operation, remote clients, and enterprise registry behavior.

## User Stories

1. As a release reviewer, I want to install an optional MCP extra, so that MCP
   support does not affect the base install.
2. As a CLI user, I want MCP resource and prompt inspection commands to work
   without the MCP SDK, so that I can audit the boundary without optional
   dependencies.
3. As an MCP client user, I want to start a local stdio MCP server, so that an
   MCP-compatible client can read Agent Harness evidence.
4. As a reviewer, I want to list allowlisted MCP resources, so that I can see
   what evidence is available without scanning the filesystem.
5. As a reviewer, I want to read run summary and context manifest resources, so
   that I can inspect a run through a standard resource interface.
6. As a reviewer, I want to read eval, retrieval, template, skill, and policy
   resources, so that related Agent Harness evidence is available through one
   boundary.
7. As a security reviewer, I want denied and sensitive resources to be blocked
   or redacted, so that MCP access cannot bypass policy.
8. As a provider-evidence reviewer, I want provider evidence to expose only
   redacted summaries and approved metadata, so that raw provider payloads and
   secrets never leak through MCP.
9. As a prompt user, I want deterministic review prompts, so that MCP clients
   can request consistent run, policy, approval, context, eval, template, skill,
   and retrieval reviews.
10. As a security reviewer, I want the MCP server to advertise no tools, so
    that clients cannot execute Agent Harness actions through MCP.
11. As an operator, I want every MCP resource and prompt request logged as
    metadata, so that access can be audited without recording sensitive content.
12. As a policy author, I want `--profile` to select the policy context for MCP
    reads, so that different profiles can produce different allowed or redacted
    views without granting write authority.
13. As a maintainer, I want MCP SDK code isolated under `agent_harness.mcp`, so
    that core registries, CLI commands, policy filtering, and evidence logging
    remain SDK-independent.
14. As a documentation reviewer, I want MCP docs to separate V9 behavior from
    future MCP tools, HTTP, hosted, and registry scope, so that public claims stay
    aligned with implemented behavior.
15. As a release reviewer, I want an MCP boundary demo and release-readiness
    gates, so that V9 can be accepted from a clean checkout.

## Behavioral Requirements

1. A user can run `agent-harness mcp resources list --json` without the MCP SDK
   installed and receive a machine-readable list of allowlisted resources.
2. A user can run `agent-harness mcp resources read
   agent-harness://runs/<run-id>/summary --json` and receive a safe resource
   envelope for an existing run summary.
3. A user can run `agent-harness mcp resources read
   agent-harness://runs/<run-id>/context --json` and receive a policy-filtered
   context manifest envelope.
4. The system rejects `file://`, absolute paths, traversal, query or fragment
   abuse, unknown URI shapes, and unsafe identifiers with safe diagnostics.
5. Unknown runs, missing artifacts, and malformed artifacts return safe error or
   denial envelopes without leaking machine-local paths.
6. Provider evidence resources return only redacted provider evidence and
   approved metadata, never raw provider requests or responses.
7. Template, skill, and policy resources resolve through their existing
   registries and services rather than raw filesystem reads.
8. Prompt list and prompt get commands return deterministic prompt metadata,
   rendered content, resource references, and stable prompt hashes.
9. Prompt rendering rejects invalid arguments and never asks clients to bypass
   policy, mutate files, approve actions, execute providers, or use tools.
10. `agent-harness mcp serve` fails clearly with an `agent-harness[mcp]`
    install hint when the MCP SDK is missing.
11. With the MCP SDK installed, `agent-harness mcp serve` starts a local stdio
    server that declares only resources and prompts.
12. The stdio MCP server responds to resource list/read and prompt list/get
    requests with protocol-valid messages and sends diagnostics to stderr.
13. No MCP tools are declared or advertised.
14. Every resource and prompt access appends a metadata-only
    `mcp_access_log.v1` JSONL record under `.agent-harness/mcp/access-log.jsonl`.
15. Access evidence records transport, profile, request type, resource URI or
    prompt name, run id when applicable, policy decision id when applicable,
    result, redaction status, and denial reason when applicable.
16. MCP reads do not mutate run summaries, artifact indexes, approval records,
    tool state, provider state, eval results, template metadata, skill metadata,
    config files, policy files, or workspace files.
17. Release readiness reports MCP boundary evidence once V9 is implemented.

## Implementation Decisions

- Add a new `agent_harness.mcp` package for V9 MCP boundary behavior.
- Keep `agent_harness.runtimes.mcp_adapter` unsupported unless a later runtime
  track explicitly implements task execution through MCP.
- Use the official MCP Python SDK package `mcp>=1,<2` only for stdio server
  integration.
- Keep URI parsing, resource registry, prompt registry, response models,
  policy filtering, CLI inspection commands, and access evidence logging
  independent of the MCP SDK.
- Add optional extra `mcp = ["mcp>=1,<2"]`.
- Add CLI group:
  - `agent-harness mcp serve [--profile PROFILE]`
  - `agent-harness mcp resources list [--profile PROFILE] [--json]`
  - `agent-harness mcp resources read <uri> [--profile PROFILE] [--json]`
  - `agent-harness mcp prompts list [--json]`
  - `agent-harness mcp prompts get <name> [--arg key=value] [--json]`
- Default `--profile` to `default`; unknown profiles fail clearly and selected
  profiles are recorded in access evidence.
- Use allowlisted `agent-harness://` resources only:
  - `agent-harness://runs`
  - `agent-harness://runs/{run_id}/summary`
  - `agent-harness://runs/{run_id}/context`
  - `agent-harness://runs/{run_id}/events`
  - `agent-harness://runs/{run_id}/tools`
  - `agent-harness://runs/{run_id}/approvals`
  - `agent-harness://runs/{run_id}/provider-evidence`
  - `agent-harness://runs/{run_id}/security-findings`
  - `agent-harness://runs/{run_id}/eval`
  - `agent-harness://runs/{run_id}/retrieval-scorecard`
  - `agent-harness://templates`
  - `agent-harness://templates/{template_id}`
  - `agent-harness://skills`
  - `agent-harness://skills/{skill_id}`
  - `agent-harness://policies/{profile}`
- Use safe MIME types only: `application/json`, `text/markdown`, and
  `text/plain`.
- Use resource response envelopes with schema version, URI, MIME type, resource
  type, source artifact, source schema version, policy profile, policy decision
  id, redaction status, denial status, content, and metadata.
- Add deterministic review prompts:
  - `agent-harness-run-review`
  - `agent-harness-policy-review`
  - `agent-harness-approval-review`
  - `agent-harness-context-review`
  - `agent-harness-eval-review`
  - `agent-harness-template-review`
  - `agent-harness-skill-review`
  - `agent-harness-retrieval-review`
- Store MCP access evidence as append-only JSONL at
  `.agent-harness/mcp/access-log.jsonl`.
- Treat access logging as the only allowed mutation in V9 MCP reads.

## Testing Decisions

- Test V9 through public interfaces: CLI commands, persisted artifacts, MCP
  stdio protocol messages, release-readiness reports, and documentation checks.
- Unit tests should cover URI parsing, allowlist behavior, response and prompt
  model serialization, prompt hashing, prompt argument validation, profile
  selection, redaction, access-log schema, and optional dependency diagnostics.
- Integration tests should cover resource list/read, prompt list/get, run
  summary, context manifest, events, approvals, provider evidence redaction,
  templates, skills, policies, denied resource behavior, and access logging.
- MCP protocol tests should use the official SDK client path when the optional
  extra is available and verify capabilities, list/read/get behavior, valid
  stdout framing, stderr diagnostics, and no advertised tools.
- Adversarial tests should cover arbitrary file URI attempts, traversal,
  absolute paths, unknown runs, denied artifacts, raw provider payload requests,
  secret or env-var requests, nonexistent tool requests, policy-bypass prompt
  attempts, write-action prompt attempts, query/fragment abuse, and unsafe ids.
- E2E tests should cover `examples/mcp_boundary/`, the V9 golden path, and
  release-readiness MCP gates.
- The required gates are docs check, pytest, Ruff, mypy, compileall, and release
  readiness. A real external MCP client smoke test may be optional if it is
  practical and non-flaky.

## Out of Scope

- MCP tools.
- Write-capable MCP actions.
- MCP approval actions.
- MCP run execution.
- MCP provider execution.
- Patch application through MCP.
- Git commit through MCP.
- Template application through MCP.
- Skill mutation through MCP.
- Arbitrary filesystem access.
- `agent-harness://files/...`, `agent-harness://workspace/...`,
  `agent-harness://env/...`, `agent-harness://secrets/...`, and
  `agent-harness://provider-raw/...` resources.
- Streamable HTTP MCP.
- Hosted MCP service.
- Remote MCP gateway.
- Enterprise MCP registry.
- Multi-agent orchestration.
- Production identity, multi-user auth, or cloud deployment.
- Replacing the CLI or operator UI.

## Further Notes

The main design tradeoff is intentionally proving evidence exposure before any
execution capability. Resources and prompts are enough to demonstrate MCP
interoperability without expanding Agent Harness mutation authority.

The largest risks are accidental raw artifact exposure, provider payload leaks,
overbroad URI parsing, SDK coupling in core code, and documentation that implies
MCP tools or hosted behavior. The implementation should keep these risks visible
through allowlists, denial envelopes, access logs, docs checks, and release
readiness.

V9 is complete only when this command path works from a clean checkout with the
MCP extra installed:

```bash
uv sync --extra mcp
uv run agent-harness demo provider-audit
uv run agent-harness mcp resources list --json
uv run agent-harness mcp resources read agent-harness://runs/<run-id>/summary --json
uv run agent-harness mcp resources read agent-harness://runs/<run-id>/context --json
uv run agent-harness mcp prompts list --json
uv run agent-harness mcp prompts get agent-harness-run-review --json
uv run agent-harness release readiness
```
