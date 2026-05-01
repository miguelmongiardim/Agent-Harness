from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from agent_harness.config import load_config
from agent_harness.evidence.schema import EvidenceCheckResult, EvidenceDiagnostic
from agent_harness.utils import load_json, normalize_relative_path

REQUIRED_GOVERNANCE_EXPORTS: tuple[tuple[str, str], ...] = (
    ("governance_summary.v1", "governance_summary.v1.json"),
    ("governance_report.v1", "governance_report.v1.json"),
    ("governance_index.v1", "governance_index.v1.json"),
    ("governance_findings.v1", "governance_findings.v1.json"),
)

GOVERNANCE_EXPORT_HINT = "agent-harness governance export --output .agent-harness/governance/"


def run_evidence_check(project_root: Path) -> EvidenceCheckResult:
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
    return run_evidence_check(project_root)


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
            f"missing V12 governance export prerequisite: {schema_version}; "
            f"generate it first with `{GOVERNANCE_EXPORT_HINT}`"
        ),
        artifact_reference=reference,
    )


def _malformed_governance_export(schema_version: str, reference: str) -> EvidenceDiagnostic:
    return EvidenceDiagnostic(
        severity="error",
        domain="evidence",
        message=(
            f"malformed V12 governance export prerequisite: {schema_version}; "
            f"regenerate it with `{GOVERNANCE_EXPORT_HINT}`"
        ),
        artifact_reference=reference,
    )


def _project_relative(root: Path, path: Path) -> str:
    try:
        return normalize_relative_path(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return path.name
