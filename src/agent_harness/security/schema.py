from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.utils import normalize_relative_path, now_utc

SecuritySeverity = Literal["critical", "high", "medium", "low", "info"]
SecurityPolicyAction = Literal["block", "report"]


class SecurityFinding(StrictModel):
    schema_version: Literal["security_finding.v1"] = "security_finding.v1"
    finding_id: str
    rule_id: str
    severity: SecuritySeverity
    scanner: str
    source: str = ""
    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    location: dict[str, str | int] = Field(default_factory=dict)
    message: str
    evidence: str | None = None
    policy_action: SecurityPolicyAction = "report"
    blocking: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    @model_validator(mode="after")
    def hydrate_security_evidence_fields(self) -> SecurityFinding:
        if not self.source:
            self.source = self.scanner
        if not self.location and self.path is not None:
            location: dict[str, str | int] = {"path": self.path}
            if self.line is not None:
                location["line"] = self.line
            self.location = location
        return self

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_relative_path(value)


class SecurityGateDecision(StrictModel):
    status: Literal["passed", "failed"]
    fail_threshold: SecuritySeverity
    blocking_finding_ids: list[str] = Field(default_factory=list)


class SecurityFindingsReport(StrictModel):
    schema_version: Literal["security_findings.v1"] = "security_findings.v1"
    run_id: str
    task_id: str
    scanner: str = "first_party_static"
    findings: list[SecurityFinding] = Field(default_factory=list)
    gate: SecurityGateDecision
    created_at: datetime = Field(default_factory=now_utc)
