from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent_harness.utils import normalize_relative_path, now_utc, sha256_json

ToolName = Literal["read_file", "search_code", "run_tests", "patch_file", "git_status"]
Sensitivity = Literal["public", "internal", "confidential", "secret"]
RunStatus = Literal["completed", "paused", "failed", "dry_run"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class HarnessConfig(StrictModel):
    schema_version: Literal["config.v1"]
    project_name: str
    artifact_root: str = ".agent-harness"
    default_policy: str = "default"
    retrieval_backend: Literal["fake", "lexical", "qdrant"] = "lexical"
    template_catalog: str = "bundled"

    @field_validator("artifact_root")
    @classmethod
    def validate_artifact_root(cls, value: str) -> str:
        return normalize_relative_path(value)


class TaskSpec(StrictModel):
    schema_version: Literal["task.v1"]
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    policy_profile: str = "default"
    target_paths: list[str] = Field(default_factory=list)
    allowed_tools: list[ToolName] | None = None
    context_queries: list[str] = Field(default_factory=list)
    test_commands: list[list[str]] = Field(default_factory=list)
    max_steps: int = Field(default=8, ge=1, le=50)

    @field_validator("target_paths")
    @classmethod
    def validate_target_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]

    @field_validator("test_commands")
    @classmethod
    def validate_test_commands(cls, commands: list[list[str]]) -> list[list[str]]:
        for command in commands:
            if not command or any(not part for part in command):
                raise ValueError("test commands must be non-empty argv arrays")
        return commands


class SensitivityRule(StrictModel):
    pattern: str
    classification: Sensitivity


class PolicyProfile(StrictModel):
    schema_version: Literal["policy.v1"]
    name: str
    description: str = ""
    allowed_tools: list[ToolName] = Field(default_factory=list)
    read_roots: list[str] = Field(default_factory=lambda: ["."])
    write_roots: list[str] = Field(default_factory=list)
    deny_globs: list[str] = Field(default_factory=list)
    approval_required_tools: list[ToolName] = Field(default_factory=list)
    allowed_test_commands: list[list[str]] = Field(default_factory=list)
    allow_network: bool = False
    max_context_bytes: int = Field(default=20000, ge=1024)
    sensitivity_rules: list[SensitivityRule] = Field(default_factory=list)
    redaction_patterns: list[str] = Field(default_factory=list)

    @field_validator("read_roots", "write_roots")
    @classmethod
    def validate_roots(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]


class PolicyDecision(StrictModel):
    schema_version: Literal["policy_decision.v1"] = "policy_decision.v1"
    decision_id: str
    allowed: bool
    approval_required: bool = False
    reason: str
    matched_rules: list[str] = Field(default_factory=list)
    redactions_applied: list[str] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=now_utc)


class ToolSpec(StrictModel):
    schema_version: Literal["tool.v1"]
    name: ToolName
    description: str
    mutates_filesystem: bool = False
    requires_approval_by_default: bool = False
    argument_schema: dict[str, Any] = Field(default_factory=dict)


class ToolCall(StrictModel):
    schema_version: Literal["tool_call.v1"] = "tool_call.v1"
    action_id: str
    tool_name: ToolName
    arguments: dict[str, Any]
    reason: str
    created_at: datetime = Field(default_factory=now_utc)

    def arguments_hash(self) -> str:
        return sha256_json(self.arguments)


class ToolObservation(StrictModel):
    schema_version: Literal["tool_observation.v1"] = "tool_observation.v1"
    action_id: str
    tool_name: ToolName
    success: bool
    status: Literal["ok", "denied", "pending_approval", "failed", "dry_run"]
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime = Field(default_factory=now_utc)
    ended_at: datetime = Field(default_factory=now_utc)


class ContextSource(StrictModel):
    source_id: str
    kind: Literal["file", "ingested_doc", "retrieval"]
    path: str | None = None
    uri: str | None = None
    content_hash: str
    sensitivity: Sensitivity = "public"
    policy_decision_id: str


class ContextChunk(StrictModel):
    chunk_id: str
    source_id: str
    text: str
    content_hash: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    score: float = Field(default=1.0, ge=0.0)
    sensitivity: Sensitivity = "public"


class ContextManifest(StrictModel):
    schema_version: Literal["context_manifest.v1"] = "context_manifest.v1"
    manifest_id: str
    run_id: str
    task_id: str
    sources: list[ContextSource] = Field(default_factory=list)
    chunks: list[ContextChunk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class Checkpoint(StrictModel):
    schema_version: Literal["checkpoint.v1"] = "checkpoint.v1"
    checkpoint_id: str
    run_id: str
    task_hash: str
    manifest_hash: str
    policy_hash: str
    previous_event_hash: str | None = None
    created_at: datetime = Field(default_factory=now_utc)

    def checkpoint_hash(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class ApprovalRecord(StrictModel):
    schema_version: Literal["approval.v1"] = "approval.v1"
    approval_id: str
    run_id: str
    action_id: str
    tool_name: ToolName
    arguments_hash: str
    policy_profile: str
    checkpoint_hash: str
    proposed_effect_hash: str
    status: Literal["pending", "approved", "denied"] = "pending"
    requested_at: datetime = Field(default_factory=now_utc)
    decided_at: datetime | None = None
    actor: str | None = None
    reason: str | None = None


class RunEvent(StrictModel):
    schema_version: Literal["run_event.v1"] = "run_event.v1"
    event_id: str
    run_id: str
    type: str
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class RunSummary(StrictModel):
    schema_version: Literal["summary.v1"] = "summary.v1"
    run_id: str
    task_id: str
    status: RunStatus
    events_count: int
    approvals: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime = Field(default_factory=now_utc)
    message: str = ""


class TemplateFile(StrictModel):
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_relative_path(value)


class TemplateSpec(StrictModel):
    schema_version: Literal["template.v1"]
    name: str
    description: str
    files: list[TemplateFile]


class EvalSpec(StrictModel):
    schema_version: Literal["eval.v1"]
    eval_id: str
    title: str
    task_path: str
    expected_status: RunStatus = "dry_run"
    required_artifacts: list[str] = Field(default_factory=list)


class EvalInvariant(StrictModel):
    name: str
    passed: bool
    message: str


class EvalResult(StrictModel):
    schema_version: Literal["eval_result.v1"] = "eval_result.v1"
    eval_id: str
    title: str = ""
    passed: bool
    message: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    invariants: list[EvalInvariant] = Field(default_factory=list)
