from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.tools.schema import ToolName
from agent_harness.utils import normalize_relative_path

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
        return self
