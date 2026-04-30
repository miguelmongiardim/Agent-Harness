from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from agent_harness.config import load_config
from agent_harness.governance.schema import (
    DomainStatus,
    FindingSeverity,
    GovernanceDiagnostic,
    GovernanceDomainSummary,
    GovernanceFinding,
    GovernanceFindingCounts,
    GovernancePolicyProfileSummary,
    GovernancePolicySummary,
    GovernanceRunsSummary,
    GovernanceSummary,
    GovernanceWorkspaceSummary,
)
from agent_harness.policy import PolicyError, load_policy
from agent_harness.storage.schema import RunSummary
from agent_harness.utils import load_json, stable_id

OPTIONAL_DOMAINS = (
    "approvals",
    "provider",
    "retrieval",
    "templates",
    "skills",
    "mcp",
    "multi_agent",
    "security",
    "release_readiness",
)


def build_governance_summary(project_root: Path) -> GovernanceSummary:
    root = project_root.resolve()
    config = load_config(root)
    artifact_root = root / config.artifact_root
    policy_reference = f"policies/{config.default_policy}.json"
    diagnostics: list[GovernanceDiagnostic] = []
    findings: list[GovernanceFinding] = []
    domains: dict[str, GovernanceDomainSummary] = {}

    policy_summary = _policy_summary(
        root,
        config.default_policy,
        policy_reference,
        diagnostics,
        findings,
    )
    domains["policy"] = _policy_domain(policy_summary, diagnostics, findings)

    runs_summary, run_domain = _runs_summary(root, artifact_root, diagnostics, findings)
    domains["runs"] = run_domain
    domains.update(_optional_domain_summaries(artifact_root))

    return GovernanceSummary(
        workspace=GovernanceWorkspaceSummary(
            project_name=config.project_name,
            artifact_root=config.artifact_root,
            config_path="agent-harness.yaml",
            default_policy=config.default_policy,
            policy_path=policy_reference,
        ),
        domains=domains,
        policy=policy_summary,
        runs=runs_summary,
        finding_counts=_finding_counts(findings),
        findings=findings,
        diagnostics=diagnostics,
    )


def _policy_summary(
    root: Path,
    profile_name: str,
    policy_reference: str,
    diagnostics: list[GovernanceDiagnostic],
    findings: list[GovernanceFinding],
) -> GovernancePolicySummary:
    try:
        policy = load_policy(root, profile_name)
    except PolicyError as exc:
        diagnostics.append(
            GovernanceDiagnostic(
                severity="error",
                domain="policy",
                message=str(exc),
                artifact_reference=policy_reference,
            )
        )
        findings.append(
            _finding(
                "policy",
                "missing_evidence",
                f"Required policy profile is missing: {profile_name}",
                policy_reference,
            )
        )
        return GovernancePolicySummary(default_profile=profile_name)
    except (OSError, ValueError, ValidationError):
        diagnostics.append(
            GovernanceDiagnostic(
                severity="error",
                domain="policy",
                message="policy evidence is malformed",
                artifact_reference=policy_reference,
            )
        )
        findings.append(
            _finding(
                "policy",
                "malformed_evidence",
                "Policy profile evidence is malformed and could not be parsed",
                policy_reference,
            )
        )
        return GovernancePolicySummary(default_profile=profile_name)

    return GovernancePolicySummary(
        default_profile=profile_name,
        profiles=[
            GovernancePolicyProfileSummary(
                name=policy.name,
                schema_version=policy.schema_version,
                path=policy_reference,
            )
        ],
    )


def _policy_domain(
    policy_summary: GovernancePolicySummary,
    diagnostics: list[GovernanceDiagnostic],
    findings: list[GovernanceFinding],
) -> GovernanceDomainSummary:
    if policy_summary.profiles:
        return GovernanceDomainSummary(
            status="present",
            message="default policy profile loaded",
            evidence_refs=[policy_summary.profiles[0].path],
        )
    has_malformed_policy = any(
        finding.domain == "policy" and finding.source == "malformed_evidence"
        for finding in findings
    )
    if has_malformed_policy:
        return GovernanceDomainSummary(
            status="malformed_evidence",
            message="policy evidence malformed",
        )
    if any(diagnostic.domain == "policy" for diagnostic in diagnostics):
        return GovernanceDomainSummary(status="missing_evidence", message="policy evidence missing")
    return GovernanceDomainSummary(status="not_present", message="policy evidence not present")


def _runs_summary(
    root: Path,
    artifact_root: Path,
    diagnostics: list[GovernanceDiagnostic],
    findings: list[GovernanceFinding],
) -> tuple[GovernanceRunsSummary, GovernanceDomainSummary]:
    runs_root = artifact_root / "runs"
    if not runs_root.exists():
        return (
            GovernanceRunsSummary(),
            GovernanceDomainSummary(status="not_present", message="no run artifacts found"),
        )

    status_counts: dict[str, int] = {}
    latest_run_id: str | None = None
    latest_run_artifact: str | None = None
    latest_ended_at: str | None = None
    evidence_refs: list[str] = []
    malformed = False
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        summary_path = run_dir / "summary.json"
        reference = _project_relative(root, summary_path)
        if not summary_path.exists():
            malformed = True
            diagnostics.append(
                GovernanceDiagnostic(
                    severity="error",
                    domain="runs",
                    message="run directory is missing summary.json",
                    artifact_reference=reference,
                )
            )
            findings.append(
                _finding(
                    "runs",
                    "missing_evidence",
                    "Run directory is missing required summary evidence",
                    reference,
                )
            )
            continue
        try:
            summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError):
            malformed = True
            diagnostics.append(
                GovernanceDiagnostic(
                    severity="error",
                    domain="runs",
                    message="run summary evidence is malformed",
                    artifact_reference=reference,
                )
            )
            findings.append(
                _finding(
                    "runs",
                    "malformed_evidence",
                    "Run summary evidence is malformed and could not be parsed",
                    reference,
                )
            )
            continue
        status_counts[summary.status] = status_counts.get(summary.status, 0) + 1
        ended_at = summary.ended_at.isoformat()
        if latest_ended_at is None or ended_at >= latest_ended_at:
            latest_ended_at = ended_at
            latest_run_id = summary.run_id
            latest_run_artifact = reference

    runs_summary = GovernanceRunsSummary(
        total=sum(status_counts.values()),
        status_counts=status_counts,
        latest_run_id=latest_run_id,
        latest_run_artifact=latest_run_artifact,
    )
    if latest_run_artifact is not None:
        evidence_refs.append(latest_run_artifact)
    if malformed:
        status: DomainStatus = "malformed_evidence" if runs_summary.total == 0 else "present"
        return runs_summary, GovernanceDomainSummary(status=status, evidence_refs=evidence_refs)
    if runs_summary.total:
        return (
            runs_summary,
            GovernanceDomainSummary(
                status="present",
                message="run summaries loaded",
                evidence_refs=evidence_refs,
            ),
        )
    return (
        runs_summary,
        GovernanceDomainSummary(status="not_present", message="no run summaries found"),
    )


def _optional_domain_summaries(artifact_root: Path) -> dict[str, GovernanceDomainSummary]:
    run_dirs = _run_dirs(artifact_root)
    return {
        "approvals": _optional_status(
            any(any((run_dir / "approvals").glob("*.json")) for run_dir in run_dirs),
            "approval evidence",
        ),
        "provider": _optional_status(
            any(
                (run_dir / name).exists()
                for run_dir in run_dirs
                for name in ("provider.json", "provider_calls.json", "provider_input.json")
            ),
            "provider evidence",
        ),
        "retrieval": _optional_status(
            _has_children(artifact_root / "indexes")
            or _has_children(artifact_root / "retrieval-scorecards"),
            "retrieval evidence",
        ),
        "templates": _optional_status(
            (artifact_root / "workspace.json").exists()
            or any((run_dir / "template_apply.json").exists() for run_dir in run_dirs),
            "template evidence",
        ),
        "skills": _optional_status(
            any((run_dir / "skill_manifest.json").exists() for run_dir in run_dirs),
            "skill evidence",
        ),
        "mcp": _optional_status(
            _has_children(artifact_root / "mcp") or _has_children(artifact_root / "mcp-access-log"),
            "MCP evidence",
        ),
        "multi_agent": _optional_status(
            _has_children(artifact_root / "orchestrations")
            or _has_children(artifact_root / "benchmarks" / "comparisons"),
            "multi-agent evidence",
        ),
        "security": _optional_status(
            _has_security_evidence(run_dirs, artifact_root),
            "security evidence",
        ),
        "release_readiness": _optional_status(
            _has_children(artifact_root / "release"),
            "release readiness evidence",
        ),
    }


def _optional_status(present: bool, label: str) -> GovernanceDomainSummary:
    return GovernanceDomainSummary(
        status="present" if present else "not_present",
        message=f"{label} {'found' if present else 'not present'}",
    )


def _run_dirs(artifact_root: Path) -> list[Path]:
    runs_root = artifact_root / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


def _has_children(path: Path) -> bool:
    return path.exists() and any(path.iterdir())


def _has_security_evidence(run_dirs: list[Path], artifact_root: Path) -> bool:
    if _has_children(artifact_root / "advisories"):
        return True
    for run_dir in run_dirs:
        findings_path = run_dir / "security_findings.json"
        if not findings_path.exists():
            continue
        try:
            loaded = load_json(findings_path)
        except (OSError, ValueError):
            return True
        if isinstance(loaded, list) and loaded:
            return True
        if isinstance(loaded, dict):
            findings = loaded.get("findings")
            if isinstance(findings, list) and findings:
                return True
    return False


def _finding_counts(findings: list[GovernanceFinding]) -> GovernanceFindingCounts:
    by_severity: dict[FindingSeverity, int] = {}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    return GovernanceFindingCounts(total=len(findings), by_severity=by_severity)


def _finding(
    domain: str,
    source: str,
    message: str,
    artifact_reference: str,
) -> GovernanceFinding:
    return GovernanceFinding(
        finding_id=stable_id("governance", domain, source, artifact_reference, message),
        severity="medium",
        domain=domain,
        source=source,
        message=message,
        artifact_reference=artifact_reference,
        evidence_refs=[artifact_reference],
        recommendation="Regenerate or restore the required local evidence artifact.",
        blocks_release=False,
    )


def _project_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name
