# MCP Boundary

This document defines the V9 MCP Boundary release for `v1.6.0` and the
implemented local read-only MCP behavior. V11 adds read-only orchestration
evidence resources to the same boundary without adding MCP tools or execution.

## Implemented in V9

Agent Harness exposes a local, read-only MCP boundary under:

```text
agent_harness.mcp
```

The boundary is for interoperability over existing Agent Harness evidence. It is
not a runtime adapter and it does not replace the CLI, runtime, policy engine,
approval service, storage layer, operator UI, template system, skill system, or
provider gateway.

The V9 implementation supports:

- read-only MCP resources
- MCP prompts
- local stdio MCP server
- CLI resource and prompt inspection
- optional `agent-harness[mcp]` dependency for `mcp serve`
- policy-filtered MCP artifacts
- MCP access evidence
- safe denial envelopes for unsupported or denied requests

The SDK-specific server integration belongs inside `agent_harness.mcp`. The core
resource registry, prompt registry, URI parsing, response models, policy
filtering, CLI inspection commands, and access logging should remain
SDK-independent.

## CLI Contract

The CLI surface is:

```bash
agent-harness mcp serve [--profile PROFILE]
agent-harness mcp resources list [--profile PROFILE] [--json]
agent-harness mcp resources read <uri> [--profile PROFILE] [--json]
agent-harness mcp prompts list [--json]
agent-harness mcp prompts get <name> [--arg key=value] [--json]
```

Resource and prompt inspection commands work without the MCP SDK. The stdio
server command starts a local MCP server when `agent-harness[mcp]` is installed
and fails with a clear install hint when the SDK is missing.

## Resource Surface

The implemented allowlist is:

```text
agent-harness://runs
agent-harness://runs/{run_id}/summary
agent-harness://runs/{run_id}/context
agent-harness://runs/{run_id}/events
agent-harness://runs/{run_id}/tools
agent-harness://runs/{run_id}/approvals
agent-harness://runs/{run_id}/provider-evidence
agent-harness://runs/{run_id}/security-findings
agent-harness://runs/{run_id}/eval
agent-harness://runs/{run_id}/retrieval-scorecard
agent-harness://templates
agent-harness://templates/{template_id}
agent-harness://skills
agent-harness://skills/{skill_id}
agent-harness://policies/{profile}
agent-harness://orchestrations
agent-harness://orchestrations/{orchestration_id}/summary
agent-harness://orchestrations/{orchestration_id}/manifest
agent-harness://orchestrations/{orchestration_id}/events
agent-harness://orchestrations/{orchestration_id}/children
agent-harness://orchestrations/{orchestration_id}/handoffs
```

The resource registry must reject arbitrary URI schemes, filesystem paths,
traversal, unsafe identifiers, query and fragment abuse, unknown resource
shapes, and mutation-shaped orchestration resource requests such as run,
approve, or resume.

V11 release readiness reads the orchestration summary and handoff resources
from `examples/orchestration_workflow/` and verifies metadata-only access-log
records for those reads.

Resource responses should use only:

```text
application/json
text/markdown
text/plain
```

Binary resources are out of scope for V9.

## Resource Envelope

Resource reads should return an envelope with:

```text
schema_version
uri
mime_type
resource_type
source_artifact
source_schema_version
policy_profile
policy_decision_id
redaction_applied
denial_status
content
metadata
```

Denied resources should return a safe denial envelope. Missing or malformed
artifacts should return safe diagnostics. Responses must not expose machine-local
filesystem internals beyond safe relative artifact paths.

## Prompt Surface

The V9 prompt registry includes:

```text
agent-harness-run-review
agent-harness-policy-review
agent-harness-approval-review
agent-harness-context-review
agent-harness-eval-review
agent-harness-template-review
agent-harness-skill-review
agent-harness-retrieval-review
```

Prompt responses should include:

```text
schema_version
name
description
mime_type
arguments
resource_references
messages
prompt_hash
denial_status
metadata
```

Prompts are review aids. They may reference allowed MCP resources, but they must
not request policy bypass, write actions, approval mutation, provider execution,
hidden files, unsupported capabilities, or private generated citation markers.

## Policy And Evidence Boundary

MCP resource and prompt requests are untrusted external access to local
artifacts. The selected policy profile is the permission context for the
response and is recorded in access evidence.

Allowed mutation is limited to append-only MCP access evidence:

```text
.agent-harness/mcp/access-log.jsonl
```

The access log schema is `mcp_access_log.v1` and records metadata only:

```text
schema_version
timestamp
transport
client_id if available
request_type
resource_uri or prompt_name
run_id if applicable
orchestration_id if applicable
artifact_type
policy_profile
policy_decision_id
result
redaction_applied
denial_reason if applicable
prompt_hash if applicable
```

MCP reads must not mutate run summaries, artifact indexes, approval records,
tool state, provider state, eval results, template metadata, skill metadata,
config files, policy files, or workspace files.

## Roadmap / Not implemented yet

The following remain future-only and must not be described as V9 behavior:

- MCP tools
- write-capable MCP
- MCP approval actions
- MCP run execution
- MCP provider execution
- patch application through MCP
- git commit through MCP
- orchestration run/approve/resume through MCP
- template application through MCP
- skill mutation through MCP
- arbitrary filesystem resources
- raw provider payload resources
- environment or secret resources
- Streamable HTTP MCP
- hosted MCP service
- remote MCP gateway
- enterprise MCP registry
- MCP runtime adapter behavior
- parallel, nested, hosted, or write-capable MCP orchestration

The existing `agent_harness.runtimes.mcp_adapter` can remain unsupported for V9.
If a later release implements MCP runtime behavior, it needs its own PRD, plan,
policy model, approval model, and release evidence.
