from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from agent_harness.model.schema import ProviderUseApprovalBinding
from agent_harness.schema_base import StrictModel
from agent_harness.tools.schema import ApprovalSubjectName
from agent_harness.utils import normalize_relative_path, now_utc, sha256_json

RunStatus = Literal["completed", "paused", "failed", "dry_run"]


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
    provider_use_binding: ProviderUseApprovalBinding | None = None


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


class AppliedTemplateRecord(StrictModel):
    template_id: str
    version: str
    destination: str
    run_id: str
    action_id: str
    evidence: str = ""
    applied_at: datetime = Field(default_factory=now_utc)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("evidence")
    @classmethod
    def validate_evidence(cls, value: str) -> str:
        return normalize_relative_path(value) if value else value


class TemplateSkillRecommendationRecord(StrictModel):
    skill_id: str
    template_id: str
    template_version: str
    destination: str
    run_id: str
    action_id: str
    evidence: str = ""
    recorded_at: datetime = Field(default_factory=now_utc)

    @field_validator("destination", "evidence")
    @classmethod
    def validate_relative_reference(cls, value: str) -> str:
        return normalize_relative_path(value) if value else value


class WorkspaceMetadata(StrictModel):
    schema_version: Literal["workspace_metadata.v1"] = "workspace_metadata.v1"
    applied_templates: list[AppliedTemplateRecord] = Field(default_factory=list)
    skill_recommendations: list[TemplateSkillRecommendationRecord] = Field(default_factory=list)
