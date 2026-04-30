from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.tools.schema import ToolName
from agent_harness.utils import normalize_relative_path, now_utc, sha256_json

OrchestrationRole = Literal["planner", "implementer", "reviewer", "tester"]


class OrchestrationChild(StrictModel):
    child_id: str = Field(min_length=1)
    role: OrchestrationRole
    title: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    target_paths: list[str] = Field(default_factory=list)
    allowed_tools: list[ToolName] | None = None
    depends_on: list[str] = Field(default_factory=list)
    provider_profile: str | None = None

    @field_validator("child_id")
    @classmethod
    def validate_child_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", value):
            raise ValueError("child_id must use letters, numbers, dot, underscore, or dash")
        return value

    @field_validator("target_paths")
    @classmethod
    def validate_target_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]


class OrchestrationSpec(StrictModel):
    schema_version: Literal["orchestration.v1"]
    orchestration_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    children: list[OrchestrationChild] = Field(min_length=1)

    @field_validator("orchestration_id")
    @classmethod
    def validate_orchestration_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", value):
            raise ValueError("orchestration_id must use letters, numbers, dot, underscore, or dash")
        return value

    @model_validator(mode="after")
    def validate_children(self) -> OrchestrationSpec:
        child_ids = [child.child_id for child in self.children]
        if len(child_ids) != len(set(child_ids)):
            raise ValueError("child_id values must be unique")
        missing_dependencies = sorted(
            {
                dependency
                for child in self.children
                for dependency in child.depends_on
                if dependency not in child_ids
            }
        )
        if missing_dependencies:
            raise ValueError(
                "depends_on references unknown child ids: " + ", ".join(missing_dependencies)
            )
        remaining = set(child_ids)
        completed: set[str] = set()
        while remaining:
            ready = [
                child
                for child in self.children
                if child.child_id in remaining and set(child.depends_on).issubset(completed)
            ]
            if not ready:
                raise ValueError("dependency cycle detected: " + ", ".join(sorted(remaining)))
            for child in ready:
                remaining.remove(child.child_id)
                completed.add(child.child_id)
        return self


OrchestrationStatus = Literal["completed", "dry_run", "paused", "failed"]
OrchestrationApprovalStatus = Literal["pending", "approved", "denied"]


class OrchestrationAuthority(StrictModel):
    child_id: str
    role: OrchestrationRole
    declared_tools: list[ToolName]
    role_ceiling: list[ToolName]
    effective_tools: list[ToolName]
    denied_tools: list[ToolName] = Field(default_factory=list)
    write_capable: bool = False
    provider_profile: str | None = None


class OrchestrationRiskSummary(StrictModel):
    requires_approval: bool
    write_capable_children: list[str] = Field(default_factory=list)
    provider_children: list[str] = Field(default_factory=list)


class OrchestrationPlan(StrictModel):
    schema_version: Literal["orchestration_plan.v1"] = "orchestration_plan.v1"
    orchestration_id: str
    source_spec: str
    source_spec_hash: str
    policy_profile: str
    policy_hash: str
    dry_run: bool
    children: list[OrchestrationAuthority]
    risk_summary: OrchestrationRiskSummary
    created_at: datetime = Field(default_factory=now_utc)

    def binding_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"created_at"})
        return sha256_json(payload)


class OrchestrationApprovalRecord(StrictModel):
    schema_version: Literal["orchestration_approval.v1"] = "orchestration_approval.v1"
    approval_id: str
    orchestration_id: str
    action_id: str
    tool_name: Literal["orchestration_plan"] = "orchestration_plan"
    arguments_hash: str
    policy_profile: str
    binding_hash: str
    status: OrchestrationApprovalStatus = "pending"
    requested_at: datetime = Field(default_factory=now_utc)
    decided_at: datetime | None = None
    actor: str | None = None
    reason: str | None = None


class OrchestrationChildRun(StrictModel):
    child_id: str
    role: OrchestrationRole
    title: str
    status: OrchestrationStatus
    run_id: str
    task_id: str
    materialized_task_path: str
    run_summary_artifact: str
    depends_on: list[str] = Field(default_factory=list)
    handoffs: list[dict[str, str]] = Field(default_factory=list)


class OrchestrationHandoff(StrictModel):
    schema_version: Literal["orchestration_handoff.v1"] = "orchestration_handoff.v1"
    handoff_id: str
    orchestration_id: str
    from_child_id: str
    from_run_id: str
    to_child_id: str
    artifact: str
    sensitivity: Literal["generated"] = "generated"
    policy_decision_id: str
    summary: str
    content_hash: str
    created_at: datetime = Field(default_factory=now_utc)


class OrchestrationSummary(StrictModel):
    schema_version: Literal["orchestration_summary.v1"] = "orchestration_summary.v1"
    orchestration_id: str
    title: str
    source_spec: str
    policy_profile: str
    status: OrchestrationStatus
    children: list[OrchestrationChildRun] = Field(default_factory=list)
    authority: list[OrchestrationAuthority] = Field(default_factory=list)
    events_count: int
    approvals: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime = Field(default_factory=now_utc)
    message: str = ""


class OrchestrationEvent(StrictModel):
    schema_version: Literal["orchestration_event.v1"] = "orchestration_event.v1"
    event_id: str
    orchestration_id: str
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class OrchestrationManifestChild(StrictModel):
    child_id: str
    role: OrchestrationRole
    task_path: str
    run_id: str
    run_summary_artifact: str


class OrchestrationManifestHandoff(StrictModel):
    handoff_id: str
    from_child_id: str
    from_run_id: str
    to_child_id: str
    artifact: str
    policy_decision_id: str


class OrchestrationManifest(StrictModel):
    schema_version: Literal["orchestration_manifest.v1"] = "orchestration_manifest.v1"
    orchestration_id: str
    source_spec: str
    policy_profile: str
    children: list[OrchestrationManifestChild] = Field(default_factory=list)
    handoffs: list[OrchestrationManifestHandoff] = Field(default_factory=list)


class OrchestrationArtifactIndex(StrictModel):
    schema_version: Literal["orchestration_artifact_index.v1"] = "orchestration_artifact_index.v1"
    orchestration_id: str
    artifacts: dict[str, str]
    artifact_hashes: dict[str, str]
