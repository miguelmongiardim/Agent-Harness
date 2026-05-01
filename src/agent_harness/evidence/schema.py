from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from agent_harness.schema_base import StrictModel
from agent_harness.utils import now_utc

EvidenceDiagnosticSeverity = Literal["info", "warning", "error"]
EvidenceCheckStatus = Literal["passed", "failed", "invalid", "internal_error"]


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
