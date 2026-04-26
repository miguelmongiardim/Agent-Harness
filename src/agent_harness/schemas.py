from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_harness.utils import normalize_relative_path, now_utc, sha256_json

ToolName = Literal[
    "read_file",
    "search_code",
    "run_tests",
    "patch_file",
    "git_status",
    "git_commit",
]
ApprovalSubjectName = Literal[
    "read_file",
    "search_code",
    "run_tests",
    "patch_file",
    "git_status",
    "git_commit",
    "provider_use",
    "provider_input",
    "template_apply",
]
Sensitivity = Literal[
    "public",
    "internal",
    "confidential",
    "restricted",
    "secret",
    "pii",
    "customer",
    "credential",
    "generated",
    "unknown",
]
RunStatus = Literal["completed", "paused", "failed", "dry_run"]
ProviderTransport = Literal["mock", "openai_compatible", "anthropic"]
TrustZone = Literal["mock", "local_process", "local_endpoint", "private_network", "hosted_provider"]
ProviderUseRuleAction = Literal["allow", "approval_required", "deny"]
ProviderInputRuleAction = Literal["allow", "allow_untrusted", "approval_required", "redact", "deny"]
ProviderCallPhase = Literal["initial_actions", "next_actions"]
ProviderExecutionMode = Literal["mock", "recorded_fixture", "live_smoke"]
RetrievalMethod = Literal["direct", "lexical", "dense", "both"]
RetrievalEvidenceMethod = Literal["lexical", "dense"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


def _validate_env_var_name(value: str) -> str:
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value):
        raise ValueError("env var names must match [A-Z_][A-Z0-9_]*")
    return value


class ProviderProfileConfig(StrictModel):
    provider_profile_id: str = Field(min_length=1)
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str = Field(min_length=1)
    endpoint_env: str
    network: bool
    requires_approval: bool = False
    api_key_env: str | None = None

    @field_validator("endpoint_env")
    @classmethod
    def validate_endpoint_env(cls, value: str) -> str:
        return _validate_env_var_name(value)

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_env_var_name(value)


class RunProviderRecord(StrictModel):
    schema_version: Literal["provider_record.v1"] = "provider_record.v1"
    provider_profile_id: str
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str
    endpoint_env: str
    endpoint_identity: str
    network: bool
    requires_approval: bool = False


class HarnessConfig(StrictModel):
    schema_version: Literal["config.v1", "config.v2"]
    project_name: str
    artifact_root: str = ".agent-harness"
    default_policy: str = "default"
    retrieval_backend: Literal["fake", "lexical", "qdrant"] = "lexical"
    template_catalog: str = "bundled"
    default_provider_profile: str | None = None
    provider_profiles: list[ProviderProfileConfig] = Field(default_factory=list)

    @field_validator("artifact_root")
    @classmethod
    def validate_artifact_root(cls, value: str) -> str:
        return normalize_relative_path(value)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> HarnessConfig:
        if self.schema_version == "config.v1":
            if self.default_provider_profile is not None or self.provider_profiles:
                raise ValueError("config.v1 does not support provider profiles")
            return self
        configured = [profile.provider_profile_id for profile in self.provider_profiles]
        if len(configured) != len(set(configured)):
            raise ValueError("provider_profile_id values must be unique")
        if (
            self.default_provider_profile is not None
            and self.default_provider_profile not in configured
        ):
            raise ValueError(
                "default_provider_profile must reference a configured provider profile"
            )
        return self


class TaskSpec(StrictModel):
    schema_version: Literal["task.v1", "task.v2"]
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    policy_profile: str = "default"
    provider_profile: str | None = None
    target_paths: list[str] = Field(default_factory=list)
    allowed_tools: list[ToolName] | None = None
    deny_provider_input_sensitivities: list[Sensitivity] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def validate_provider_profile_usage(self) -> TaskSpec:
        if self.schema_version == "task.v1" and self.provider_profile is not None:
            raise ValueError("task.v1 does not support provider_profile")
        return self


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
    provider_trust_policy: dict[TrustZone, ProviderUseRuleAction] = Field(default_factory=dict)
    provider_input_policy: dict[Sensitivity, ProviderInputRuleAction] = Field(default_factory=dict)
    hard_deny_sensitivities: list[Sensitivity] = Field(default_factory=list)
    provider_input_redact_reclassify: dict[Sensitivity, Sensitivity] = Field(default_factory=dict)
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


class RetrievalProvenance(StrictModel):
    method: RetrievalEvidenceMethod
    score: float = Field(default=0.0, ge=0.0)


class DenseRetrievalMetadata(StrictModel):
    backend: str
    model: str
    version: str


class ContextManifestItem(StrictModel):
    item_id: str
    source_id: str
    chunk_id: str
    source_kind: Literal["file", "retrieval"]
    path: str | None = None
    content_hash: str | None = None
    text: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    sensitivity: Sensitivity = "public"
    retrieval_method: RetrievalMethod
    provenance: list[RetrievalProvenance] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    policy_allowed: bool
    policy_decision_id: str
    policy_reason: str


class ContextManifest(StrictModel):
    schema_version: Literal["context_manifest.v1", "context_manifest.v2"] = (
        "context_manifest.v2"
    )
    manifest_id: str
    run_id: str
    task_id: str
    sources: list[ContextSource] = Field(default_factory=list)
    chunks: list[ContextChunk] = Field(default_factory=list)
    items: list[ContextManifestItem] = Field(default_factory=list)
    rejected_items: list[ContextManifestItem] = Field(default_factory=list)
    dense_retrieval: DenseRetrievalMetadata | None = None
    created_at: datetime = Field(default_factory=now_utc)


class ProviderInputRecord(StrictModel):
    record_id: str
    manifest_item_id: str | None = None
    source_id: str
    chunk_id: str
    path: str | None = None
    sensitivity: Sensitivity
    effective_sensitivity: Sensitivity
    policy_action: ProviderInputRuleAction
    included: bool
    untrusted: bool = False
    redaction_status: Literal["none", "redacted", "reclassified"] = "none"
    redactions_applied: list[str] = Field(default_factory=list)
    trust_zone: TrustZone
    provider_profile_id: str
    approval_id: str | None = None
    policy_decision_id: str
    policy_reason: str
    text: str | None = None
    content_hash: str | None = None


class ProviderInputManifest(StrictModel):
    schema_version: Literal["provider_input.v1"] = "provider_input.v1"
    run_id: str
    task_id: str
    provider_profile_id: str
    trust_zone: TrustZone
    records: list[ProviderInputRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class ProviderCallAudit(StrictModel):
    schema_version: Literal["provider_call_audit.v1"] = "provider_call_audit.v1"
    audit_id: str
    run_id: str
    task_id: str
    provider_profile_id: str
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str
    endpoint_identity: str
    network: bool
    phase: ProviderCallPhase
    mode: ProviderExecutionMode
    fixture_id: str | None = None
    approval_ids: list[str] = Field(default_factory=list)
    action_count: int = 0
    actions_hash: str
    created_at: datetime = Field(default_factory=now_utc)


class ProviderCallAuditManifest(StrictModel):
    schema_version: Literal["provider_calls.v1"] = "provider_calls.v1"
    run_id: str
    task_id: str
    provider_profile_id: str
    calls: list[ProviderCallAudit] = Field(default_factory=list)
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
    tool_name: ApprovalSubjectName
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


class TemplateRegistryRecord(StrictModel):
    schema_version: Literal["template_registry_record.v1"] = "template_registry_record.v1"
    template_id: str
    version: str
    title: str
    description: str
    bundle_path: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("bundle_path")
    @classmethod
    def validate_bundle_path(cls, value: str) -> str:
        return normalize_relative_path(value)


class TemplateDetail(StrictModel):
    schema_version: Literal["template_detail.v1"] = "template_detail.v1"
    template_id: str
    version: str
    title: str
    description: str
    bundle_path: str
    tags: list[str] = Field(default_factory=list)
    files: list[TemplateFile]


class TemplateProposedWrite(StrictModel):
    path: str
    before_hash: str
    after_hash: str
    diff: str
    proposed_content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_relative_path(value)


class TemplateApplyRecord(StrictModel):
    schema_version: Literal["template_apply.v1"] = "template_apply.v1"
    template_id: str
    version: str
    title: str
    description: str
    destination: str
    proposed_writes: list[TemplateProposedWrite]
    force: bool = False

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        return normalize_relative_path(value)


class AppliedTemplateRecord(StrictModel):
    template_id: str
    version: str
    destination: str
    run_id: str
    action_id: str
    applied_at: datetime = Field(default_factory=now_utc)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        return normalize_relative_path(value)


class WorkspaceMetadata(StrictModel):
    schema_version: Literal["workspace_metadata.v1"] = "workspace_metadata.v1"
    applied_templates: list[AppliedTemplateRecord] = Field(default_factory=list)


class GitCommitPlan(StrictModel):
    schema_version: Literal["git_commit.v1"] = "git_commit.v1"
    run_id: str
    action_id: str
    parent_head: str
    file_set: list[str]
    content_hashes: dict[str, str]
    diff: str
    diff_hash: str
    final_message: str = Field(min_length=1)
    final_message_hash: str
    policy_profile: str
    checkpoint_hash: str
    approved_patch_action_ids: list[str]
    commit_hash: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    committed_at: datetime | None = None

    @field_validator("file_set")
    @classmethod
    def validate_file_set(cls, values: list[str]) -> list[str]:
        normalized = [normalize_relative_path(value) for value in values]
        if not normalized:
            raise ValueError("git_commit requires at least one approved file")
        if normalized != sorted(set(normalized)):
            raise ValueError("git_commit file_set must be sorted and unique")
        return normalized


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
