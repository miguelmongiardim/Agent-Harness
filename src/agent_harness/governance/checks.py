from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from agent_harness.governance.schema import (
    FindingSeverity,
    GovernanceCheckResult,
    GovernanceDiagnostic,
    GovernanceFinding,
    safe_artifact_reference,
)
from agent_harness.governance.summary import build_governance_summary
from agent_harness.utils import load_json, stable_id

RAW_PROVIDER_PAYLOAD_NAMES = (
    "raw_provider_payload.json",
    "provider_raw.json",
    "raw_provider_request.json",
    "raw_provider_response.json",
    "raw_request.json",
    "raw_response.json",
)


def run_governance_check(project_root: Path) -> GovernanceCheckResult:
    root = project_root.resolve()
    try:
        summary = build_governance_summary(root)
    except (OSError, ValueError, ValidationError):
        return GovernanceCheckResult(
            status="invalid",
            exit_code=2,
            diagnostics=[
                GovernanceDiagnostic(
                    severity="error",
                    domain="governance",
                    message="governance input, config, or artifact root is invalid",
                )
            ],
        )
    except Exception:
        return GovernanceCheckResult(
            status="internal_error",
            exit_code=3,
            diagnostics=[
                GovernanceDiagnostic(
                    severity="error",
                    domain="governance",
                    message="governance check failed with an internal error",
                )
            ],
        )

    artifact_root = root / summary.workspace.artifact_root
    findings = [
        *_default_blocking_findings(summary.findings),
        *_raw_provider_payload_findings(root, artifact_root),
        *_unsafe_artifact_reference_findings(root, artifact_root),
        *_docs_check_findings(root, artifact_root),
    ]
    blocking_findings = [finding for finding in findings if finding.blocks_release]
    advisory_findings = [finding for finding in findings if not finding.blocks_release]
    exit_code = 1 if blocking_findings else 0
    return GovernanceCheckResult(
        status="failed" if blocking_findings else "passed",
        exit_code=exit_code,
        blocking_findings=len(blocking_findings),
        advisory_findings=len(advisory_findings),
        findings=findings,
        diagnostics=summary.diagnostics,
    )


def _default_blocking_findings(findings: list[GovernanceFinding]) -> list[GovernanceFinding]:
    normalized: list[GovernanceFinding] = []
    for finding in findings:
        if finding.severity == "critical" and not finding.blocks_release:
            normalized.append(finding.model_copy(update={"blocks_release": True}))
        else:
            normalized.append(finding)
    return normalized


def _raw_provider_payload_findings(root: Path, artifact_root: Path) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    for run_dir in _run_dirs(artifact_root):
        for name in RAW_PROVIDER_PAYLOAD_NAMES:
            payload_path = run_dir / name
            if not payload_path.exists():
                continue
            reference = _project_relative(root, payload_path)
            findings.append(
                _finding(
                    domain="provider",
                    source="raw_provider_payload",
                    severity="critical",
                    message=(
                        "Raw provider payload artifact is present and is excluded "
                        "from governance output"
                    ),
                    artifact_reference=reference,
                    recommendation=(
                        "Remove the raw payload artifact and retain only redacted "
                        "provider evidence."
                    ),
                    blocks_release=True,
                )
            )
    return findings


def _unsafe_artifact_reference_findings(root: Path, artifact_root: Path) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    for summary_path in _run_summary_paths(artifact_root):
        try:
            summary = load_json(summary_path)
        except (OSError, ValueError):
            continue
        if not isinstance(summary, dict):
            continue
        artifacts = summary.get("artifacts")
        if not isinstance(artifacts, dict):
            continue
        for index, reference in enumerate(artifacts.values(), start=1):
            if not isinstance(reference, str) or _is_safe_artifact_reference(root, reference):
                continue
            summary_reference = _project_relative(root, summary_path)
            findings.append(
                _finding(
                    domain="runs",
                    source="unsafe_artifact_reference",
                    severity="critical",
                    message=f"Run summary contains unsafe artifact reference #{index}",
                    artifact_reference=summary_reference,
                    recommendation=(
                        "Regenerate the run summary with normalized project-relative "
                        "artifact references."
                    ),
                    blocks_release=True,
                )
            )
    return findings


def _docs_check_findings(root: Path, artifact_root: Path) -> list[GovernanceFinding]:
    report_path = artifact_root / "docs" / "docs-check.json"
    if not report_path.exists():
        return []
    report_reference = _project_relative(root, report_path)
    try:
        report = load_json(report_path)
    except (OSError, ValueError):
        return [
            _finding(
                domain="docs",
                source="malformed_evidence",
                severity="medium",
                message="Docs check evidence is malformed and could not be parsed",
                artifact_reference=report_reference,
                recommendation="Regenerate docs check evidence.",
                blocks_release=False,
            )
        ]
    if not isinstance(report, dict):
        return []
    docs_findings = report.get("findings")
    if not isinstance(docs_findings, list):
        return []
    findings: list[GovernanceFinding] = []
    for docs_finding in docs_findings:
        rule_id = _safe_rule_id(docs_finding)
        findings.append(
            _finding(
                domain="docs",
                source="docs_check",
                severity="medium",
                message=f"Docs check finding remains advisory: {rule_id}",
                artifact_reference=report_reference,
                recommendation="Resolve docs check findings before release.",
                blocks_release=False,
            )
        )
    return findings


def _safe_rule_id(value: object) -> str:
    if not isinstance(value, dict):
        return "unknown_rule"
    rule_id = value.get("rule_id")
    if not isinstance(rule_id, str):
        return "unknown_rule"
    return "".join(ch for ch in rule_id if ch.isalnum() or ch in "_.-")[:80] or "unknown_rule"


def _is_safe_artifact_reference(root: Path, reference: str) -> bool:
    try:
        normalized = safe_artifact_reference(reference)
        (root / normalized).resolve().relative_to(root)
    except ValueError:
        return False
    return True


def _run_dirs(artifact_root: Path) -> list[Path]:
    runs_root = artifact_root / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


def _run_summary_paths(artifact_root: Path) -> list[Path]:
    return [
        run_dir / "summary.json"
        for run_dir in _run_dirs(artifact_root)
        if (run_dir / "summary.json").exists()
    ]


def _finding(
    *,
    domain: str,
    source: str,
    severity: FindingSeverity,
    message: str,
    artifact_reference: str,
    recommendation: str,
    blocks_release: bool,
) -> GovernanceFinding:
    return GovernanceFinding(
        finding_id=stable_id(
            "governance",
            domain,
            source,
            severity,
            artifact_reference,
            message,
        ),
        severity=severity,
        domain=domain,
        source=source,
        message=message,
        artifact_reference=artifact_reference,
        evidence_refs=[artifact_reference],
        recommendation=recommendation,
        blocks_release=blocks_release,
    )


def _project_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name
