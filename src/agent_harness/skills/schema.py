from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from agent_harness.schema_base import StrictModel
from agent_harness.utils import now_utc

SkillSourceType = Literal["bundled", "local", "direct_path"]
SkillCompatibilityStatus = Literal["compatible", "incompatible"]


class SkillSpec(StrictModel):
    schema_version: Literal["skill.v1"]
    skill_id: str
    name: str = Field(min_length=1)
    version: str
    description: str = Field(min_length=1)
    category: str = Field(min_length=1)
    compatible_agent_harness_versions: str = Field(min_length=1)
    required_capabilities: list[str]
    allowed_context_classes: list[str] = Field(default_factory=list)
    default_policy_profile: str | None = None
    related_skills: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)

    @field_validator("skill_id")
    @classmethod
    def validate_skill_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise ValueError("skill_id must be lowercase kebab-case")
        return value

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        if not re.fullmatch(r"\d+\.\d+\.\d+", value):
            raise ValueError("version must use MAJOR.MINOR.PATCH")
        return value


class SkillValidationReport(StrictModel):
    schema_version: Literal["skill_validation.v1"] = "skill_validation.v1"
    status: Literal["passed", "failed"]
    skill_id: str | None = None
    source_type: SkillSourceType
    source: str
    compatibility_status: SkillCompatibilityStatus = "compatible"
    skill_hash: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class SkillRegistryRecord(StrictModel):
    schema_version: Literal["skill_registry_record.v1"] = "skill_registry_record.v1"
    skill_id: str
    version: str
    name: str
    description: str
    source_type: SkillSourceType
    source: str
    compatibility_status: SkillCompatibilityStatus = "compatible"
    validation_status: Literal["passed", "failed"]
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class SkillDetail(StrictModel):
    schema_version: Literal["skill_detail.v1"] = "skill_detail.v1"
    skill_id: str
    name: str
    version: str
    description: str
    category: str
    compatible_agent_harness_versions: str
    required_capabilities: list[str] = Field(default_factory=list)
    allowed_context_classes: list[str] = Field(default_factory=list)
    default_policy_profile: str | None = None
    related_skills: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    source_type: SkillSourceType
    source: str
    compatibility_status: SkillCompatibilityStatus = "compatible"
    validation_status: Literal["passed", "failed"]
    skill_hash: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    body_summary: str


class SkillRequestedBy(StrictModel):
    kind: Literal["task", "template"]
    reference: str
    field: str
    required: bool


class SkillResolutionRecord(StrictModel):
    skill_id: str
    resolution_status: Literal["resolved", "missing", "invalid"]
    required: bool
    requested_by: list[SkillRequestedBy]
    version: str | None = None
    source_type: SkillSourceType | None = None
    source: str | None = None
    compatibility_status: SkillCompatibilityStatus | None = None
    validation_status: Literal["passed", "failed"] | None = None
    skill_hash: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class SkillResolutionReport(StrictModel):
    schema_version: Literal["skill_resolution.v1"] = "skill_resolution.v1"
    status: Literal["passed", "failed"]
    task_id: str
    task_path: str
    skills: list[SkillResolutionRecord] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    authority: dict[str, Any]


class SkillManifestRecord(StrictModel):
    skill_id: str
    version: str | None = None
    source_type: SkillSourceType | None = None
    source: str | None = None
    skill_hash: str | None = None
    required: bool
    requested_by: list[SkillRequestedBy]
    resolution_time: datetime = Field(default_factory=now_utc)
    resolution_status: Literal["resolved", "missing", "invalid"]
    inclusion_status: Literal["included", "rejected", "not_included"]
    policy_decision_id: str | None = None
    context_manifest_id: str | None = None
    context_manifest_item_id: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class SkillManifest(StrictModel):
    schema_version: Literal["skill_manifest.v1"] = "skill_manifest.v1"
    run_id: str
    task_id: str
    context_manifest_id: str | None = None
    skills: list[SkillManifestRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
