# Plan: Agent Harness V9 MCP Boundary

> Source PRD: [docs/prd-agent-harness-v9.md](../docs/prd-agent-harness-v9.md)

V9 targets `v1.6.0`. This plan is intentionally sliced around observable
read-only MCP boundary behavior. Implementation should proceed with TDD, one
public behavior at a time.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness mcp serve`,
  `agent-harness mcp resources list/read`, and
  `agent-harness mcp prompts list/get`; inspection commands work without the
  MCP SDK, while `serve` requires `agent-harness[mcp]`.
- **Key models**: add SDK-independent models for MCP resource listings,
  resource read envelopes, prompt listings, rendered prompt responses, and
  `mcp_access_log.v1`.
- **Schema**: resource envelopes include URI, MIME type, resource type, source
  artifact, source schema version, selected policy profile, policy decision id,
  redaction status, denial status, content, and metadata.
- **Storage**: write append-only metadata evidence to
  `.agent-harness/mcp/access-log.jsonl`; do not update run summaries, artifact
  indexes, approvals, provider state, eval results, templates, skills, config,
  policy, or workspace files during MCP reads.
- **Runtime boundary**: V9 is not a runtime. `agent_harness.runtimes.mcp_adapter`
  remains unsupported unless a later track explicitly implements MCP task
  execution.
- **MCP boundary**: new code lives under `agent_harness.mcp`; only stdio server
  integration depends on the official `mcp>=1,<2` SDK.
- **Policy boundary**: selected profiles filter resource exposure and redaction
  but never grant tools, writes, approvals, provider execution, or wider context
  than policy permits.
- **Approval model**: MCP can read approval evidence, but cannot create, approve,
  deny, resume, or mutate approvals.
- **Audit model**: every resource and prompt request appends metadata-only MCP
  access evidence, including denials and redactions.
- **External service boundary**: V9 is local stdio only. HTTP, Streamable HTTP,
  hosted MCP, remote gateways, and registry behavior are roadmap-only.

---

## Phase 0: V9 Scope Is Documented And Guarded

**User stories covered**

- Story 14: documentation reviewer can separate V9 MCP boundary behavior from
  later MCP execution or hosted scope.
- Story 15: release reviewer can see the planned V9 acceptance path before code
  changes begin.

**Observable behaviors**

- V9 PRD and plan exist.
- MCP boundary docs identify `agent_harness.mcp` as the planned boundary and
  explicitly state that V9 is not a runtime adapter.
- Current docs do not claim MCP behavior as implemented before V9 code lands.

**First RED test**

- `agent-harness docs check` fails if current capability docs claim MCP tools,
  write-capable MCP, HTTP MCP, hosted MCP, or MCP runtime adapter behavior
  outside roadmap/future sections.

### What to build

Add the V9 PRD, vertical-slice plan, and MCP boundary docs. Update README,
roadmap, architecture, security, and release-readiness docs with planned V9
scope and guarded future language.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v9.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v9.md` exists and uses vertical slices.
- [x] `docs/mcp-boundary.md` explains the V9 boundary.
- [x] README and roadmap link to the V9 docs without claiming current MCP
      support.
- [x] Architecture docs identify `agent_harness.mcp` as the planned boundary
      and keep `runtimes.mcp_adapter` out of V9.
- [x] Security docs state the planned V9 read-only MCP boundary and exclusions.
- [x] Release-readiness docs name planned MCP gates.
- [x] Docs check passes.

### Phase 0 implementation notes

- Added docs-check coverage for unsupported V9 MCP implemented-scope claims via
  `unsupported_mcp_scope_claim`.
- Guarded MCP tools, write-capable MCP, HTTP/Streamable HTTP MCP, hosted MCP,
  and MCP runtime adapter behavior outside roadmap, out-of-scope,
  not-implemented, and future sections.
- Verified current docs still pass `agent-harness docs check` with zero
  findings.

### Out of scope

- Any MCP CLI implementation.
- Optional dependency changes.
- Resource or prompt registry code.

---

## Phase 1: CLI User Can Discover And Read A Safe Run Resource

**User stories covered**

- Story 1: optional MCP extra does not affect base install.
- Story 2: CLI inspection works without the MCP SDK.
- Story 4: reviewer can list allowlisted resources.
- Story 5: reviewer can read a run summary or context manifest.

**Observable behaviors**

- `agent-harness mcp resources list --json` works without the MCP extra.
- `agent-harness mcp resources read agent-harness://runs/<run-id>/summary --json`
  returns a safe envelope for an existing run.
- `agent-harness mcp serve` fails with an `agent-harness[mcp]` install hint when
  the SDK is absent.

**First RED test**

- A CLI test creates a provider-audit run, calls `mcp resources list --json` and
  `mcp resources read .../summary --json`, and fails because no MCP CLI group or
  SDK-independent registry exists.

### What to build

Add the optional dependency declaration, CLI group, SDK availability diagnostic,
safe URI parser, minimal resource registry, and run summary/context read
envelopes through `RunStore`.

### Acceptance criteria

- [x] Base install works without MCP dependencies.
- [x] `agent-harness mcp serve` fails clearly when `mcp` is missing.
- [x] `agent-harness mcp resources list [--profile PROFILE] [--json]` exists.
- [x] `agent-harness mcp resources read <uri> [--profile PROFILE] [--json]`
      exists.
- [x] `agent-harness://runs` lists available run summary resources.
- [x] Run summary and context resources resolve through artifact storage.
- [x] CLI help states V9 is resources/prompts only.
- [x] CLI inspection commands do not import the MCP SDK.

### Phase 1 implementation notes

- Added the optional `mcp = ["mcp>=1,<2"]` extra and refreshed `uv.lock`.
- Added an SDK-independent `agent_harness.mcp` resource boundary for listing
  runs and reading run summary/context envelopes from `RunStore` artifacts.
- Added `agent-harness mcp resources list/read --json` and a placeholder
  `agent-harness mcp serve` command that reports the missing SDK with an
  `agent-harness[mcp]` install hint.
- Verified default `uv run` has no `mcp` module installed while resource
  inspection commands pass.

### Out of scope

- Stdio server implementation.
- Full resource surface.
- Prompt registry.
- Release-readiness MCP gates.

---

## Phase 2: Unsafe Resource Reads Are Denied And Logged

**User stories covered**

- Story 7: denied and sensitive resources are blocked or redacted.
- Story 11: access is recorded as evidence.
- Story 12: profile selection is recorded and affects resource reads.

**Observable behaviors**

- Attempts to read `file://`, traversal, absolute path, unknown URI shapes, or
  unsafe identifiers return safe denial envelopes.
- Allowed and denied reads append metadata-only `mcp_access_log.v1` records.
- `--profile` selects the policy context and unknown profiles fail clearly.

**First RED test**

- An adversarial CLI test reads `file://...` and expects a safe denial envelope
  plus an access-log entry, but no denial/access evidence path exists.

### What to build

Complete URI validation, profile loading, denial envelopes, safe diagnostics,
and append-only MCP access logging for resource reads.

### Acceptance criteria

- [ ] Unknown resource URI fails clearly.
- [ ] Path traversal fails.
- [ ] Arbitrary `file://` URI fails.
- [ ] Absolute path attempts fail.
- [ ] Query and fragment abuse fails.
- [ ] Unsafe run ids fail.
- [ ] Unknown profiles fail clearly.
- [ ] Selected profiles are recorded in access evidence.
- [ ] Allowed reads are logged.
- [ ] Denied reads are logged.
- [ ] Logs omit raw returned content, secrets, env values, and provider raw
      payloads.

### Out of scope

- Provider evidence resources.
- Prompt access logging.
- MCP protocol server.

---

## Phase 3: Reviewer Can Inspect Templates, Skills, And Policies Through MCP Resources

**User stories covered**

- Story 6: reviewer can read template, skill, and policy resources.
- Story 7: policy filtering still applies.
- Story 13: SDK-independent registries remain usable by CLI.

**Observable behaviors**

- `agent-harness://templates` and `agent-harness://templates/{template_id}` read
  through the template registry.
- `agent-harness://skills` and `agent-harness://skills/{skill_id}` read through
  the skill registry.
- `agent-harness://policies/{profile}` reads through the policy service.

**First RED test**

- An integration test reads a bundled template and bundled skill through MCP
  resource CLI commands and fails because the registry only supports run
  artifacts.

### What to build

Extend the resource registry to cover template records/details, skill
records/details or rendered safe guidance, and policy summaries through existing
public boundaries.

### Acceptance criteria

- [ ] Template list resource works.
- [ ] Template detail resource works.
- [ ] Skill list resource works.
- [ ] Skill detail or safe rendered skill resource works.
- [ ] Policy summary resource works.
- [ ] Resource responses record source artifact and source schema version where
      available.
- [ ] No resource reads raw filesystem paths directly.

### Out of scope

- Template application.
- Skill mutation or creation.
- Policy mutation.
- MCP prompts.

---

## Phase 4: Reviewer Can Inspect Run Evidence Without Provider Payload Leaks

**User stories covered**

- Story 6: reviewer can inspect eval and retrieval resources.
- Story 8: provider evidence exposes only redacted metadata.
- Story 11: reads are audited.

**Observable behaviors**

- Run events, tool/action evidence, approvals, security findings, eval results,
  retrieval scorecards, and provider evidence are available where present.
- Provider evidence never returns raw provider request or response payloads.

**First RED test**

- An integration test reads `agent-harness://runs/<run-id>/provider-evidence`
  and asserts redacted provider-call metadata is returned while raw payload
  shapes are absent.

### What to build

Complete the run resource surface using existing storage and inspect/operator
artifact patterns. Add provider-evidence shaping that returns only approved
redacted artifacts, summaries, hashes, policy decision ids, and metadata.

### Acceptance criteria

- [ ] Events resource works where available.
- [ ] Tool calls resource works where available.
- [ ] Approval resource works where available.
- [ ] Provider evidence resource returns redacted evidence only.
- [ ] Security findings resource works.
- [ ] Eval resource works where available.
- [ ] Retrieval scorecard resource works where available.
- [ ] Missing artifacts return safe envelopes.
- [ ] Malformed artifacts return safe diagnostics.
- [ ] Resource reads do not mutate run summaries or artifact indexes.

### Out of scope

- MCP prompt registry.
- MCP protocol server.
- Release-readiness automation.

---

## Phase 5: Reviewer Can Retrieve Deterministic Review Prompts

**User stories covered**

- Story 9: prompt user can retrieve deterministic review prompts.
- Story 11: prompt access is logged.
- Story 14: prompt docs distinguish prompts from tools.

**Observable behaviors**

- `agent-harness mcp prompts list --json` lists all V9 review prompts.
- `agent-harness mcp prompts get agent-harness-run-review --json` returns a
  deterministic prompt response with a stable hash.
- Invalid arguments fail clearly.
- Prompt requests append access evidence.

**First RED test**

- A CLI test calls `mcp prompts list --json` and
  `mcp prompts get agent-harness-run-review --json`, expecting a stable
  `prompt_hash`, but no prompt registry exists.

### What to build

Add SDK-independent prompt registry and response models for run, policy,
approval, context, eval, template, skill, and retrieval review prompts.

### Acceptance criteria

- [ ] Prompt list works.
- [ ] Prompt get works.
- [ ] Prompt arguments validate.
- [ ] Prompt output is deterministic for the same arguments.
- [ ] Prompt hash is stable.
- [ ] Prompt responses include referenced allowed resources.
- [ ] Prompts do not request policy bypass.
- [ ] Prompts do not request write actions.
- [ ] Prompts do not request approval mutation.
- [ ] Prompts do not request provider execution.
- [ ] Prompt access evidence is emitted.

### Out of scope

- MCP stdio server.
- Prompt execution authority.
- External client smoke tests.

---

## Phase 6: MCP Client Can Use The Local Stdio Server

**User stories covered**

- Story 3: MCP client user can start a local stdio server.
- Story 10: server advertises no tools.
- Story 13: SDK code stays isolated under `agent_harness.mcp`.

**Observable behaviors**

- With `agent-harness[mcp]` installed, `agent-harness mcp serve` starts a stdio
  MCP server.
- Protocol initialization declares resources and prompts only.
- Resource list/read and prompt list/get work through the same registries as
  CLI commands.
- Tools are not advertised.

**First RED test**

- An optional MCP protocol test starts the stdio server with the SDK client and
  expects resources/prompts capabilities but no tools.

### What to build

Use the official MCP Python SDK package under `agent_harness.mcp` to implement
stdio transport and protocol handlers backed by the existing registries.

### Acceptance criteria

- [ ] Server declares resources/prompts only.
- [ ] Server does not declare tools.
- [ ] Server responds to resources/list.
- [ ] Server responds to resources/read.
- [ ] Server responds to prompts/list.
- [ ] Server responds to prompts/get.
- [ ] Server emits only valid MCP messages on stdout.
- [ ] Diagnostics go to stderr.
- [ ] No HTTP transport exists in V9.
- [ ] SDK-specific code remains isolated under `agent_harness.mcp`.

### Out of scope

- Streamable HTTP.
- Hosted service.
- Remote client gateway.
- MCP tools.

---

## Phase 7: Demo And Release Readiness Close V9

**User stories covered**

- Story 15: release reviewer can accept V9 from a clean checkout.
- Story 14: docs stay aligned with implemented behavior.
- Story 10: no MCP tools are advertised in release evidence.

**Observable behaviors**

- `examples/mcp_boundary/` demonstrates the V9 golden path.
- Release readiness verifies MCP extra install path, CLI resource/prompt
  behavior, denial behavior, access evidence, and stdio capabilities.
- Docs checks keep MCP tools, HTTP, hosted, and runtime-adapter claims out of
  implemented sections.

**First RED test**

- `agent-harness release readiness` passes even though no MCP demo evidence,
  access log, or no-tools protocol evidence exists.

### What to build

Add the MCP boundary example, expected resource/prompt/denial outputs, optional
protocol smoke evidence, release-readiness MCP gates, CI installation of the
MCP extra for relevant jobs, and docs claim guards.

### Acceptance criteria

- [ ] `examples/mcp_boundary/README.md` documents the V9 golden path.
- [ ] Expected resources list, prompts list, and denied resource examples exist.
- [ ] Release readiness verifies MCP extra installed in the CI path.
- [ ] Release readiness verifies MCP CLI commands exist.
- [ ] Release readiness verifies `mcp resources list --json` succeeds.
- [ ] Release readiness verifies summary and context resource reads succeed.
- [ ] Release readiness verifies prompt list/get succeeds.
- [ ] Release readiness verifies denied resource behavior.
- [ ] Release readiness verifies access log emission.
- [ ] Release readiness verifies stdio server advertises resources/prompts only.
- [ ] Release readiness verifies stdio server does not advertise tools.
- [ ] Docs do not claim MCP tools, HTTP, hosted service, or runtime adapter
      behavior as implemented.
- [ ] Final V9 golden path works from a clean checkout.

### Out of scope

- Release tagging.
- Package publishing.
- External MCP client as a mandatory gate.

## Cross-Phase Invariants

- MCP is a read-only interoperability boundary over existing evidence.
- V9 MCP behavior lives under `agent_harness.mcp`, not runtime adapters.
- CLI resource and prompt inspection remain SDK-independent.
- Only `agent-harness mcp serve` requires the MCP SDK.
- MCP never grants tools, approvals, provider calls, run creation, template
  application, skill mutation, patch application, git commit, or writes.
- MCP never reads arbitrary files, env vars, secrets, ignored caches, or raw
  provider payloads.
- Every resource URI is allowlisted and must use the `agent-harness://` scheme.
- Policy profiles remain permission ceilings and are recorded in access
  evidence.
- Access logging is metadata-only and append-only.
- Denials and redactions are observable and logged.
- Resource responses use safe MIME types only.
- Tests verify behavior through public CLI, persisted artifacts, protocol
  messages, docs checks, and release reports.
- No roadmap feature enters implementation without a testable public behavior.
