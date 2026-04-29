from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator

from agent_harness.schema_base import StrictModel

RunStatus = Literal["completed", "paused", "failed", "dry_run"]


def _validate_skill_id_list(values: list[str], field_name: str) -> list[str]:
    for value in values:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", value):
            raise ValueError(f"{field_name} must use lowercase kebab-case skill ids")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} values must be unique")
    return values


class EvalSpec(StrictModel):
    schema_version: Literal["eval.v1"]
    eval_id: str
    title: str
    task_path: str
    expected_status: RunStatus = "dry_run"
    required_artifacts: list[str] = Field(default_factory=list)
    expected_skills: list[str] = Field(default_factory=list)

    @field_validator("expected_skills")
    @classmethod
    def validate_expected_skills(cls, values: list[str]) -> list[str]:
        return _validate_skill_id_list(values, "expected_skills")


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
