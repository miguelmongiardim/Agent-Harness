from __future__ import annotations

from datetime import datetime
from pathlib import PureWindowsPath
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
CheckStatus = Literal["passed", "failed", "invalid", "internal_error"]
EvidenceRedactionStatus = Literal[
    "safe",
    "redacted",
    "metadata_only",
    "excluded_raw",
    "unknown",
]
EvidenceInclusionStatus = Literal["included", "excluded", "missing", "malformed"]


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


class GovernanceCheckResult(StrictModel):
    schema_version: Literal["governance_check.v1"] = "governance_check.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    status: CheckStatus
    exit_code: int
    blocking_findings: int = 0
    advisory_findings: int = 0
    findings: list[GovernanceFinding] = Field(default_factory=list)
    diagnostics: list[GovernanceDiagnostic] = Field(default_factory=list)


class GovernanceReportSection(StrictModel):
    section_id: str
    title: str
    status: DomainStatus | CheckStatus | str
    message: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class GovernanceReport(StrictModel):
    schema_version: Literal["governance_report.v1"] = "governance_report.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    summary: GovernanceSummary
    check: GovernanceCheckResult
    sections: list[GovernanceReportSection] = Field(default_factory=list)
    findings: list[GovernanceFinding] = Field(default_factory=list)
    diagnostics: list[GovernanceDiagnostic] = Field(default_factory=list)


class GovernanceIndexEntry(StrictModel):
    artifact_type: str
    path: str
    content_hash: str | None = None
    source_run_id: str | None = None
    schema_version: str | None = None
    redaction_status: EvidenceRedactionStatus = "unknown"
    inclusion_status: EvidenceInclusionStatus = "included"


class GovernanceIndex(StrictModel):
    schema_version: Literal["governance_index.v1"] = "governance_index.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    entries: list[GovernanceIndexEntry] = Field(default_factory=list)


class GovernanceFindingsExport(StrictModel):
    schema_version: Literal["governance_findings.v1"] = "governance_findings.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    counts: GovernanceFindingCounts = Field(default_factory=GovernanceFindingCounts)
    findings: list[GovernanceFinding] = Field(default_factory=list)


class GovernanceExportResult(StrictModel):
    schema_version: Literal["governance_export.v1"] = "governance_export.v1"
    output_path: str
    files: list[str] = Field(default_factory=list)


def safe_artifact_reference(reference: str) -> str:
    if PureWindowsPath(reference).is_absolute():
        raise ValueError("absolute paths are not allowed")
    return normalize_relative_path(reference)
