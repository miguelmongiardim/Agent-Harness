from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from agent_harness.schema_base import StrictModel
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
