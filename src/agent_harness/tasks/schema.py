from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.policy.schema import Sensitivity
from agent_harness.schema_base import StrictModel
from agent_harness.tools.schema import ToolName
from agent_harness.utils import normalize_relative_path


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
    skills: list[str] = Field(default_factory=list)
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

    @field_validator("skills")
    @classmethod
    def validate_task_skills(cls, values: list[str]) -> list[str]:
        return _validate_skill_id_list(values, "task skills")

    @model_validator(mode="after")
    def validate_provider_profile_usage(self) -> TaskSpec:
        if self.schema_version == "task.v1" and self.provider_profile is not None:
            raise ValueError("task.v1 does not support provider_profile")
        if self.schema_version == "task.v1" and self.skills:
            raise ValueError("task.v1 does not support skills")
        return self


def _validate_skill_id_list(values: list[str], field_name: str) -> list[str]:
    for value in values:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise ValueError(f"{field_name} must use lowercase kebab-case skill ids")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} values must be unique")
    return values
