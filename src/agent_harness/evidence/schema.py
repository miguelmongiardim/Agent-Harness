from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_harness.schema_base import StrictModel
from agent_harness.utils import now_utc

EvidenceDiagnosticSeverity = Literal["info", "warning", "error"]
EvidenceCheckStatus = Literal["passed", "failed", "invalid", "internal_error"]
EvidenceExportStatus = Literal["passed", "failed", "invalid", "internal_error"]
EvidenceRedactionStatus = Literal["safe", "redacted", "metadata_only", "excluded_raw", "unknown"]
EvidenceInclusionStatus = Literal["included", "excluded", "missing", "malformed"]
EvidenceClaimStatus = Literal["non_certifying"]
EvidenceFindingSeverity = Literal["critical", "high", "medium", "low", "info"]
EvidenceDomainStatus = Literal[
    "present",
    "not_present",
    "missing_evidence",
    "malformed_evidence",
    "blocked_by_policy",
    "roadmap_only",
]

NON_CERTIFICATION_DISCLAIMER = (
    "This evidence pack supports review and audit preparation. It does not certify "
    "compliance with any legal, regulatory, security, or organizational framework."
)


class EvidenceDiagnostic(StrictModel):
    severity: EvidenceDiagnosticSeverity
    domain: str
    message: str
    artifact_reference: str | None = None


class EvidenceCheckResult(StrictModel):
    schema_version: Literal["evidence_check.v1"] = "evidence_check.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    status: EvidenceCheckStatus
    exit_code: int
    diagnostics: list[EvidenceDiagnostic] = Field(default_factory=list)


class EvidenceWorkspaceIdentity(StrictModel):
    project_name: str
    artifact_root: str
    config_path: str
    default_policy: str
    policy_path: str


class EvidenceDomainSummary(StrictModel):
    status: EvidenceDomainStatus
    message: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class EvidencePack(StrictModel):
    schema_version: Literal["evidence_pack.v1"] = "evidence_pack.v1"
    pack_id: str
    generated_at: datetime = Field(default_factory=now_utc)
    profile: str
    agent_harness_version: str
    workspace: EvidenceWorkspaceIdentity
    domains: dict[str, EvidenceDomainSummary] = Field(default_factory=dict)
    governance_references: list[str]
    governance_hashes: dict[str, str]
    release_readiness_reference: str | None = None
    redaction_status: EvidenceRedactionStatus = "metadata_only"
    claim_status: EvidenceClaimStatus = "non_certifying"
    disclaimer: str = NON_CERTIFICATION_DISCLAIMER


class EvidenceManifestFile(StrictModel):
    path: str
    schema_version: str | None = None
    redaction_status: EvidenceRedactionStatus = "metadata_only"


class EvidenceManifest(StrictModel):
    schema_version: Literal["evidence_manifest.v1"] = "evidence_manifest.v1"
    pack_id: str
    generated_at: datetime = Field(default_factory=now_utc)
    files: list[EvidenceManifestFile] = Field(default_factory=list)


class EvidenceIndexEntry(StrictModel):
    artifact_type: str
    path: str
    content_hash: str | None = None
    schema_version: str | None = None
    redaction_status: EvidenceRedactionStatus = "metadata_only"
    inclusion_status: EvidenceInclusionStatus = "included"


class EvidenceIndex(StrictModel):
    schema_version: Literal["evidence_index.v1"] = "evidence_index.v1"
    pack_id: str
    generated_at: datetime = Field(default_factory=now_utc)
    entries: list[EvidenceIndexEntry] = Field(default_factory=list)


class EvidenceFinding(StrictModel):
    schema_version: Literal["evidence_finding.v1"] = "evidence_finding.v1"
    finding_id: str
    severity: EvidenceFindingSeverity
    domain: str
    source: str
    message: str
    artifact_reference: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    omission_reason: str | None = None
    recommendation: str = ""
    blocks_release: bool = False
    blocks_evidence_pack: bool = False


class EvidenceFindingCounts(StrictModel):
    total: int = 0
    by_severity: dict[EvidenceFindingSeverity, int] = Field(default_factory=dict)


class EvidenceFindingsExport(StrictModel):
    schema_version: Literal["evidence_findings.v1"] = "evidence_findings.v1"
    pack_id: str
    generated_at: datetime = Field(default_factory=now_utc)
    counts: EvidenceFindingCounts = Field(default_factory=EvidenceFindingCounts)
    findings: list[EvidenceFinding] = Field(default_factory=list)


class EvidenceExportResult(StrictModel):
    schema_version: Literal["evidence_export_result.v1"] = "evidence_export_result.v1"
    generated_at: datetime = Field(default_factory=now_utc)
    status: EvidenceExportStatus
    exit_code: int
    output_path: str
    files: list[str] = Field(default_factory=list)
    diagnostics: list[EvidenceDiagnostic] = Field(default_factory=list)
