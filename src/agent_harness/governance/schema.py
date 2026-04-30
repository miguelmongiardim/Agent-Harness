from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_harness.schema_base import StrictModel
from agent_harness.utils import normalize_relative_path, now_utc

DomainStatus = Literal[
    "present",
    "not_present",
    "missing_evidence",
    "malformed_evidence",
    "blocked_by_policy",
    "roadmap_only",
]
FindingSeverity = Literal["critical", "high", "medium", "low", "info"]
DiagnosticSeverity = Literal["info", "warning", "error"]


class GovernanceDomainSummary(StrictModel):
    status: DomainStatus
    message: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class GovernanceWorkspaceSummary(StrictModel):
    project_name: str
    artifact_root: str
    config_path: str
    default_policy: str
    policy_path: str


class GovernancePolicyProfileSummary(StrictModel):
    name: str
    schema_version: str
    path: str


class GovernancePolicySummary(StrictModel):
    default_profile: str
    profiles: list[GovernancePolicyProfileSummary] = Field(default_factory=list)


class GovernanceRunsSummary(StrictModel):
    total: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    latest_run_id: str | None = None
    latest_run_artifact: str | None = None


class GovernanceFinding(StrictModel):
    schema_version: Literal["governance_finding.v1"] = "governance_finding.v1"
    finding_id: str
    severity: FindingSeverity
    domain: str
    source: str
    message: str
    artifact_reference: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    recommendation: str = ""
    blocks_release: bool = False


class GovernanceDiagnostic(StrictModel):
    severity: DiagnosticSeverity
    domain: str
    message: str
    artifact_reference: str | None = None


class GovernanceFindingCounts(StrictModel):
    total: int = 0
    by_severity: dict[FindingSeverity, int] = Field(default_factory=dict)


class GovernanceSummary(StrictModel):
    schema_version: Literal["governance_summary.v1"] = "governance_summary.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    workspace: GovernanceWorkspaceSummary
    domains: dict[str, GovernanceDomainSummary]
    policy: GovernancePolicySummary
    runs: GovernanceRunsSummary
    finding_counts: GovernanceFindingCounts = Field(default_factory=GovernanceFindingCounts)
    findings: list[GovernanceFinding] = Field(default_factory=list)
    diagnostics: list[GovernanceDiagnostic] = Field(default_factory=list)


def safe_artifact_reference(reference: str) -> str:
    return normalize_relative_path(reference)
