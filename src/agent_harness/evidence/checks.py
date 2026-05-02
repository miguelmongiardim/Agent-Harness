from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from agent_harness.config import load_config
from agent_harness.evidence.schema import (
    EvidenceCheckResult,
    EvidenceDiagnostic,
    EvidenceFinding,
    EvidenceFindingsExport,
)
from agent_harness.utils import load_json, normalize_relative_path

REQUIRED_GOVERNANCE_EXPORTS: tuple[tuple[str, str], ...] = (
    ("governance_summary.v1", "governance_summary.v1.json"),
    ("governance_report.v1", "governance_report.v1.json"),
    ("governance_index.v1", "governance_index.v1.json"),
    ("governance_findings.v1", "governance_findings.v1.json"),
)

GOVERNANCE_EXPORT_HINT = "agent-harness governance export --output .agent-harness/governance/"


def run_evidence_check(project_root: Path) -> EvidenceCheckResult:
    prerequisite_result = run_evidence_prerequisite_check(project_root)
    if prerequisite_result.exit_code != 0:
        return prerequisite_result

    root = project_root.resolve()
    try:
        from agent_harness.evidence.pack import build_evidence_state

        state = build_evidence_state(root, profile="default")
    except Exception:
        return EvidenceCheckResult(
            status="internal_error",
            exit_code=3,
            diagnostics=[
                EvidenceDiagnostic(
                    severity="error",
                    domain="evidence",
                    message="evidence check failed with an internal error",
                )
            ],
        )
    blocking_diagnostics = _blocking_finding_diagnostics(state.findings_export.findings)
    if blocking_diagnostics:
        return EvidenceCheckResult(
            status="failed",
            exit_code=1,
            diagnostics=blocking_diagnostics,
        )
    existing_pack_result = _existing_pack_findings_result(root)
    if existing_pack_result is not None:
        return existing_pack_result
    return EvidenceCheckResult(status="passed", exit_code=0)


def run_evidence_prerequisite_check(project_root: Path) -> EvidenceCheckResult:
    root = project_root.resolve()
    try:
        config = load_config(root)
        artifact_root = normalize_relative_path(config.artifact_root)
    except (OSError, ValueError, ValidationError):
        return EvidenceCheckResult(
            status="invalid",
            exit_code=2,
            diagnostics=[
                EvidenceDiagnostic(
                    severity="error",
                    domain="evidence",
                    message="evidence input, config, or artifact root is invalid",
                )
            ],
        )

    governance_dir = root / artifact_root / "governance"
    diagnostics = _governance_export_diagnostics(root, governance_dir)
    if diagnostics:
        return EvidenceCheckResult(status="invalid", exit_code=2, diagnostics=diagnostics)
    return EvidenceCheckResult(status="passed", exit_code=0)


def build_missing_prerequisite_result(project_root: Path) -> EvidenceCheckResult:
    return run_evidence_prerequisite_check(project_root)


def _existing_pack_findings_result(root: Path) -> EvidenceCheckResult | None:
    try:
        config = load_config(root)
        artifact_root = normalize_relative_path(config.artifact_root)
    except (OSError, ValueError, ValidationError):
        return EvidenceCheckResult(
            status="invalid",
            exit_code=2,
            diagnostics=[
                EvidenceDiagnostic(
                    severity="error",
                    domain="evidence",
                    message="evidence input, config, or artifact root is invalid",
                )
            ],
        )
    findings_path = root / artifact_root / "evidence" / "evidence_findings.v1.json"
    if not findings_path.exists():
        return None
    try:
        findings_export = EvidenceFindingsExport.model_validate_json(
            findings_path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError, ValidationError):
        return EvidenceCheckResult(
            status="invalid",
            exit_code=2,
            diagnostics=[
                EvidenceDiagnostic(
                    severity="error",
                    domain="evidence",
                    message="existing evidence findings artifact is malformed",
                    artifact_reference=_project_relative(root, findings_path),
                )
            ],
        )
    blocking_diagnostics = _blocking_finding_diagnostics(findings_export.findings)
    if blocking_diagnostics:
        return EvidenceCheckResult(
            status="failed",
            exit_code=1,
            diagnostics=blocking_diagnostics,
        )
    return None


def _blocking_finding_diagnostics(findings: list[EvidenceFinding]) -> list[EvidenceDiagnostic]:
    return [
        EvidenceDiagnostic(
            severity="error",
            domain=finding.domain,
            message=f"blocking evidence finding: {finding.source}",
            artifact_reference=finding.artifact_reference,
        )
        for finding in findings
        if finding.blocks_evidence_pack
    ]


def _governance_export_diagnostics(root: Path, governance_dir: Path) -> list[EvidenceDiagnostic]:
    diagnostics: list[EvidenceDiagnostic] = []
    for schema_version, filename in REQUIRED_GOVERNANCE_EXPORTS:
        path = governance_dir / filename
        reference = _project_relative(root, path)
        if not path.exists():
            diagnostics.append(_missing_governance_export(schema_version, reference))
            continue
        try:
            payload = load_json(path)
        except (OSError, ValueError):
            diagnostics.append(_malformed_governance_export(schema_version, reference))
            continue
        if not isinstance(payload, dict) or payload.get("schema_version") != schema_version:
            diagnostics.append(_malformed_governance_export(schema_version, reference))
    return diagnostics


def _missing_governance_export(schema_version: str, reference: str) -> EvidenceDiagnostic:
    return EvidenceDiagnostic(
        severity="error",
        domain="evidence",
        message=(
            f"missing v1.8.0 governance export prerequisite: {schema_version}; "
            f"generate it first with `{GOVERNANCE_EXPORT_HINT}`"
        ),
        artifact_reference=reference,
    )


def _malformed_governance_export(schema_version: str, reference: str) -> EvidenceDiagnostic:
    return EvidenceDiagnostic(
        severity="error",
        domain="evidence",
        message=(
            f"malformed v1.8.0 governance export prerequisite: {schema_version}; "
            f"regenerate it with `{GOVERNANCE_EXPORT_HINT}`"
        ),
        artifact_reference=reference,
    )


def _project_relative(root: Path, path: Path) -> str:
    try:
        return normalize_relative_path(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return path.name
