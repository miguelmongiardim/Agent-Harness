from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.utils import normalize_relative_path

TemplateSourceType = Literal["bundled_json", "bundled_pack", "local_pack"]
TemplateCompatibilityStatus = Literal["compatible", "incompatible"]


class TemplateFile(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

    path: str
    content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_relative_path(value)


class TemplateSpec(StrictModel):
    schema_version: Literal["template.v1", "template.v2"]
    name: str
    version: str = ""
    title: str = ""
    description: str
    minimum_agent_harness_version: str | None = None
    maximum_agent_harness_version: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    generated_schema_versions: dict[str, str] = Field(default_factory=dict)
    provider_requirements: dict[str, Any] = Field(default_factory=dict)
    policy_requirements: dict[str, Any] = Field(default_factory=dict)
    retrieval_assumptions: dict[str, Any] = Field(default_factory=dict)
    eval_or_demo_metadata: dict[str, Any] = Field(default_factory=dict)
    recommended_skills: list[str] = Field(default_factory=list)
    files: list[TemplateFile]

    @field_validator("recommended_skills")
    @classmethod
    def validate_recommended_skills(cls, values: list[str]) -> list[str]:
        return _validate_skill_id_list(values, "recommended_skills")

    @model_validator(mode="after")
    def validate_template_contract(self) -> TemplateSpec:
        if self.schema_version == "template.v2":
            missing = [
                name
                for name in (
                    "minimum_agent_harness_version",
                    "required_capabilities",
                    "generated_schema_versions",
                    "provider_requirements",
                    "policy_requirements",
                    "retrieval_assumptions",
                    "eval_or_demo_metadata",
                )
                if _is_missing_template_metadata(getattr(self, name))
            ]
            if missing:
                raise ValueError(f"template.v2 missing required metadata: {', '.join(missing)}")
        return self


def _validate_skill_id_list(values: list[str], field_name: str) -> list[str]:
    for value in values:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise ValueError(f"{field_name} must use lowercase kebab-case skill ids")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} values must be unique")
    return values


def _is_missing_template_metadata(value: object) -> bool:
    return value is None or value == {} or value == []


class TemplateRegistryRecord(StrictModel):
    schema_version: Literal["template_registry_record.v1"] = "template_registry_record.v1"
    template_id: str
    version: str
    title: str
    description: str
    bundle_path: str
    source_type: TemplateSourceType = "bundled_json"
    compatibility_status: TemplateCompatibilityStatus = "compatible"
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
    source_type: TemplateSourceType = "bundled_json"
    compatibility_status: TemplateCompatibilityStatus = "compatible"
    tags: list[str] = Field(default_factory=list)
    template_schema_version: Literal["template.v1", "template.v2"] = "template.v1"
    minimum_agent_harness_version: str | None = None
    maximum_agent_harness_version: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    generated_schema_versions: dict[str, str] = Field(default_factory=dict)
    provider_requirements: dict[str, Any] = Field(default_factory=dict)
    policy_requirements: dict[str, Any] = Field(default_factory=dict)
    retrieval_assumptions: dict[str, Any] = Field(default_factory=dict)
    eval_or_demo_metadata: dict[str, Any] = Field(default_factory=dict)
    recommended_skills: list[str] = Field(default_factory=list)
    files: list[TemplateFile]


class TemplateProposedWrite(StrictModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

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
    recommended_skills: list[str] = Field(default_factory=list)

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        return normalize_relative_path(value)


__all__ = [
    "TemplateCompatibilityStatus",
    "TemplateApplyRecord",
    "TemplateDetail",
    "TemplateFile",
    "TemplateProposedWrite",
    "TemplateRegistryRecord",
    "TemplateSourceType",
    "TemplateSpec",
]
