from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_harness.schema_base import StrictModel

ArtifactStatus = Literal["available", "missing", "denied", "malformed"]


class OperatorHealthResponse(StrictModel):
    schema_version: Literal["operator_health.v1"] = "operator_health.v1"
    status: Literal["ok"] = "ok"
    agent_harness_version: str
    mode: Literal["local_operator"] = "local_operator"
    local_only: bool = True


class OperatorRunListResponse(StrictModel):
    schema_version: Literal["operator_run_list.v1"] = "operator_run_list.v1"
    runs: list[dict[str, Any]]
    count: int = Field(ge=0)


class OperatorArtifactStatus(StrictModel):
    artifact_type: str
    status: ArtifactStatus
    path: str | None = None
    detail: str | None = None


class OperatorRunDetailResponse(StrictModel):
    schema_version: Literal["operator_run_detail.v1"] = "operator_run_detail.v1"
    run_id: str
    summary: dict[str, Any]
    events: list[dict[str, Any]]
    artifact_index: dict[str, Any]
    provider: dict[str, Any] | None = None
    provider_calls: dict[str, Any] | None = None
    provider_input: dict[str, Any] | None = None
    security_findings: dict[str, Any] | None = None
    runtime_adapter: dict[str, Any] | None = None
    schema_versions: dict[str, Any] | None = None
    skill_manifest: dict[str, Any] | None = None
    template_apply: dict[str, Any] | None = None
    git_commit: dict[str, Any] | None = None
    eval_results: dict[str, Any] | None = None
    retrieval_scorecards: dict[str, Any] | None = None
    workspace_metadata: dict[str, Any] | None = None
    artifact_statuses: dict[str, OperatorArtifactStatus] = Field(default_factory=dict)


class OperatorContextResponse(StrictModel):
    schema_version: Literal["operator_context.v1"] = "operator_context.v1"
    run_id: str
    artifact: OperatorArtifactStatus
    context_manifest: dict[str, Any] | None = None


class OperatorPolicyResponse(StrictModel):
    schema_version: Literal["operator_policy.v1"] = "operator_policy.v1"
    profile: str
    policy: dict[str, Any]


class OperatorApprovalListResponse(StrictModel):
    schema_version: Literal["operator_approval_list.v1"] = "operator_approval_list.v1"
    run_id: str
    approvals: list[dict[str, Any]]
    counts: dict[str, int]


class OperatorApprovalDecisionRequest(StrictModel):
    decision: Literal["approve", "deny"]
    actor: str | None = None
    reason: str | None = None


class OperatorApprovalDecisionResponse(StrictModel):
    schema_version: Literal["operator_approval_decision.v1"] = "operator_approval_decision.v1"
    run_id: str
    approval: dict[str, Any]
