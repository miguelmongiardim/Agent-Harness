from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_harness.schema_base import StrictModel

McpDenialStatus = Literal["allowed", "denied"]


class McpResourceDescriptor(StrictModel):
    uri: str
    resource_type: str
    mime_type: str
    name: str
    description: str | None = None
    source_artifact: str | None = None


class McpResourceList(StrictModel):
    schema_version: Literal["mcp_resource_list.v1"] = "mcp_resource_list.v1"
    profile: str
    resources: list[McpResourceDescriptor]
    count: int = Field(ge=0)


class McpResourceEnvelope(StrictModel):
    schema_version: Literal["mcp_resource_envelope.v1"] = "mcp_resource_envelope.v1"
    uri: str
    mime_type: str = "application/json"
    resource_type: str
    source_artifact: str | None
    source_schema_version: Any | None
    policy_profile: str
    policy_decision_id: str | None = None
    redaction_applied: bool = False
    denial_status: McpDenialStatus
    content: Any | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class McpPromptDescriptor(StrictModel):
    name: str
    description: str
    mime_type: str
    arguments: list[str] = Field(default_factory=list)


class McpPromptList(StrictModel):
    schema_version: Literal["mcp_prompt_list.v1"] = "mcp_prompt_list.v1"
    prompts: list[McpPromptDescriptor]
    count: int = Field(ge=0)


class McpPromptMessage(StrictModel):
    role: str
    content: str


class McpPromptResponse(StrictModel):
    schema_version: Literal["mcp_prompt_response.v1"] = "mcp_prompt_response.v1"
    name: str
    description: Any | None
    mime_type: str = "text/markdown"
    arguments: dict[str, str] = Field(default_factory=dict)
    resource_references: list[str] = Field(default_factory=list)
    messages: list[McpPromptMessage] = Field(default_factory=list)
    prompt_hash: str | None
    denial_status: McpDenialStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class McpAccessLogRecord(StrictModel):
    schema_version: Literal["mcp_access_log.v1"] = "mcp_access_log.v1"
    timestamp: str
    transport: str
    request_type: str
    resource_uri: str | None = None
    prompt_name: str | None = None
    run_id: str | None = None
    orchestration_id: str | None = None
    artifact_type: str | None = None
    policy_profile: str
    policy_decision_id: str | None = None
    result: str
    redaction_applied: bool = False
    denial_reason: str | None = None
    prompt_hash: str | None = None
