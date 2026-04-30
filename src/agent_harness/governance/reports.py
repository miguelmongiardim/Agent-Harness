from __future__ import annotations

from pathlib import Path

from agent_harness.governance.checks import RAW_PROVIDER_PAYLOAD_NAMES, run_governance_check
from agent_harness.governance.schema import (
    EvidenceInclusionStatus,
    EvidenceRedactionStatus,
    FindingSeverity,
    GovernanceCheckResult,
    GovernanceExportResult,
    GovernanceFinding,
    GovernanceFindingCounts,
    GovernanceFindingsExport,
    GovernanceIndex,
    GovernanceIndexEntry,
    GovernanceReport,
    GovernanceReportSection,
    GovernanceSummary,
    safe_artifact_reference,
)
from agent_harness.governance.summary import build_governance_summary
from agent_harness.utils import hash_file, load_json, write_json

REPORT_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("policy", "Policy", "policy"),
    ("runs", "Runs", "runs"),
    ("approvals", "Approvals", "approvals"),
    ("provider", "Provider", "provider"),
    ("retrieval", "Retrieval", "retrieval"),
    ("templates", "Templates", "templates"),
    ("skills", "Skills", "skills"),
    ("mcp", "MCP", "mcp"),
    ("multi_agent", "Multi-Agent", "multi_agent"),
    ("security", "Security", "security"),
    ("release_readiness", "Release Readiness", "release_readiness"),
)

RUN_EVIDENCE_FILES: dict[str, tuple[str, EvidenceRedactionStatus]] = {
    "summary.json": ("run_summary", "safe"),
    "artifact-index.json": ("artifact_index", "safe"),
    "task.json": ("task", "safe"),
    "policy.json": ("policy", "safe"),
    "context_manifest.json": ("context_manifest", "redacted"),
    "events.jsonl": ("run_events", "metadata_only"),
    "provider.json": ("provider", "metadata_only"),
    "provider_calls.json": ("provider_calls", "metadata_only"),
    "provider_input.json": ("provider_input", "redacted"),
    "security_findings.json": ("security_findings", "safe"),
    "skill_manifest.json": ("skill_manifest", "safe"),
    "template_apply.json": ("template_application", "safe"),
    "runtime_adapter.json": ("runtime_adapter", "safe"),
    "schema_versions.json": ("schema_versions", "safe"),
    "git_commit.json": ("git_commit", "metadata_only"),
}

PROVIDER_REDACTED_DIRS = (
    ("provider/redacted-prompts", "provider_redacted_prompt"),
    ("provider/redacted-responses", "provider_redacted_response"),
)


def build_governance_report(project_root: Path) -> GovernanceReport:
    summary = build_governance_summary(project_root)
    check = run_governance_check(project_root)
    return _report_from_summary_and_check(summary, check)


def render_governance_report_markdown(report: GovernanceReport) -> str:
    lines = [
        "# Governance Report",
        "",
        f"Schema: `{report.schema_version}`",
        f"Check status: `{report.check.status}`",
        f"Blocking findings: {report.check.blocking_findings}",
        f"Advisory findings: {report.check.advisory_findings}",
        "",
    ]
    for section in report.sections:
        lines.extend(
            [
                f"## {section.title}",
                "",
                f"Status: `{section.status}`",
            ]
        )
        if section.message:
            lines.append(section.message)
        if section.evidence_refs:
            lines.append("Evidence:")
            lines.extend(f"- `{reference}`" for reference in section.evidence_refs)
        lines.append("")

    lines.extend(["## Findings", ""])
    if not report.findings:
        lines.extend(["No governance findings.", ""])
    else:
        for finding in report.findings:
            blocks = "blocking" if finding.blocks_release else "advisory"
            reference = f" `{finding.artifact_reference}`" if finding.artifact_reference else ""
            lines.append(
                f"- `{finding.severity}` `{finding.domain}` `{finding.source}` "
                f"({blocks}){reference}: {finding.message}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_governance_index(project_root: Path) -> GovernanceIndex:
    root = project_root.resolve()
    summary = build_governance_summary(root)
    artifact_root = root / summary.workspace.artifact_root
    entries: list[GovernanceIndexEntry] = []
    _append_if_exists(entries, root, root / summary.workspace.config_path, "config", "safe")
    _append_if_exists(entries, root, root / summary.workspace.policy_path, "policy", "safe")
    _append_if_exists(
        entries,
        root,
        artifact_root / "docs" / "docs-check.json",
        "docs_check",
        "safe",
    )
    _append_if_exists(
        entries,
        root,
        artifact_root / "workspace.json",
        "workspace_metadata",
        "safe",
    )

    for run_dir in _run_dirs(artifact_root):
        run_id = run_dir.name
        for filename, (artifact_type, redaction_status) in RUN_EVIDENCE_FILES.items():
            _append_if_exists(
                entries,
                root,
                run_dir / filename,
                artifact_type,
                redaction_status,
                source_run_id=run_id,
            )
        for relative_dir, artifact_type in PROVIDER_REDACTED_DIRS:
            for path in sorted((run_dir / relative_dir).glob("*.json")):
                _append_if_exists(
                    entries,
                    root,
                    path,
                    artifact_type,
                    "redacted",
                    source_run_id=run_id,
                )
        for filename in RAW_PROVIDER_PAYLOAD_NAMES:
            path = run_dir / filename
            if not path.exists():
                continue
            entry = _index_entry(
                root,
                path,
                "raw_provider_payload",
                "excluded_raw",
                "excluded",
                source_run_id=run_id,
            )
            if entry is not None:
                entries.append(entry)

    return GovernanceIndex(entries=sorted(entries, key=lambda entry: entry.path))


def export_governance(project_root: Path, output: Path | None = None) -> GovernanceExportResult:
    root = project_root.resolve()
    summary = build_governance_summary(root)
    check = run_governance_check(root)
    report = _report_from_summary_and_check(summary, check)
    index = build_governance_index(root)
    findings_export = GovernanceFindingsExport(
        counts=_finding_counts(report.findings),
        findings=report.findings,
    )
    output_dir = output or root / summary.workspace.artifact_root / "governance"
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "governance_summary.v1.json": summary.model_dump(mode="json"),
        "governance_report.v1.json": report.model_dump(mode="json"),
        "governance_index.v1.json": index.model_dump(mode="json"),
        "governance_findings.v1.json": findings_export.model_dump(mode="json"),
    }
    written: list[str] = []
    for filename, payload in files.items():
        path = output_dir / filename
        write_json(path, payload)
        written.append(_project_relative(root, path))
    markdown_path = output_dir / "governance_report.v1.md"
    markdown_path.write_text(render_governance_report_markdown(report), encoding="utf-8")
    written.append(_project_relative(root, markdown_path))

    return GovernanceExportResult(
        output_path=_project_relative(root, output_dir),
        files=sorted(written),
    )


def _report_from_summary_and_check(
    summary: GovernanceSummary,
    check: GovernanceCheckResult,
) -> GovernanceReport:
    sections = [
        _section_from_domain(summary, section_id, title, domain)
        for section_id, title, domain in REPORT_SECTIONS
    ]
    unsupported_findings = [finding for finding in check.findings if finding.domain == "docs"]
    sections.append(
        GovernanceReportSection(
            section_id="unsupported_claims",
            title="Unsupported Claims",
            status="present" if unsupported_findings else "not_present",
            message=(
                f"{len(unsupported_findings)} docs-check finding(s) visible"
                if unsupported_findings
                else "no unsupported-claim findings present"
            ),
            evidence_refs=sorted(
                {
                    reference
                    for finding in unsupported_findings
                    for reference in finding.evidence_refs
                }
            ),
        )
    )
    return GovernanceReport(
        summary=summary,
        check=check,
        sections=sections,
        findings=check.findings,
        diagnostics=check.diagnostics,
    )


def _section_from_domain(
    summary: GovernanceSummary,
    section_id: str,
    title: str,
    domain: str,
) -> GovernanceReportSection:
    domain_summary = summary.domains.get(domain)
    if domain_summary is None:
        return GovernanceReportSection(
            section_id=section_id,
            title=title,
            status="not_present",
            message=f"{title.lower()} evidence not present",
        )
    return GovernanceReportSection(
        section_id=section_id,
        title=title,
        status=domain_summary.status,
        message=domain_summary.message,
        evidence_refs=domain_summary.evidence_refs,
    )


def _append_if_exists(
    entries: list[GovernanceIndexEntry],
    root: Path,
    path: Path,
    artifact_type: str,
    redaction_status: EvidenceRedactionStatus,
    *,
    source_run_id: str | None = None,
) -> None:
    if not path.exists():
        return
    entry = _index_entry(
        root,
        path,
        artifact_type,
        redaction_status,
        "included",
        source_run_id=source_run_id,
    )
    if entry is not None:
        entries.append(entry)


def _index_entry(
    root: Path,
    path: Path,
    artifact_type: str,
    redaction_status: EvidenceRedactionStatus,
    inclusion_status: EvidenceInclusionStatus,
    *,
    source_run_id: str | None = None,
) -> GovernanceIndexEntry | None:
    try:
        reference = safe_artifact_reference(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return None
    content_hash = hash_file(path) if inclusion_status == "included" else None
    return GovernanceIndexEntry(
        artifact_type=artifact_type,
        path=reference,
        content_hash=content_hash,
        source_run_id=source_run_id,
        schema_version=_schema_version(path) if inclusion_status == "included" else None,
        redaction_status=redaction_status,
        inclusion_status=inclusion_status,
    )


def _schema_version(path: Path) -> str | None:
    if path.suffix != ".json":
        return None
    try:
        loaded = load_json(path)
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict):
        return None
    schema_version = loaded.get("schema_version")
    return schema_version if isinstance(schema_version, str) else None


def _run_dirs(artifact_root: Path) -> list[Path]:
    runs_root = artifact_root / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


def _finding_counts(findings: list[GovernanceFinding]) -> GovernanceFindingCounts:
    counts: dict[FindingSeverity, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return GovernanceFindingCounts(total=len(findings), by_severity=counts)


def _project_relative(root: Path, path: Path) -> str:
    try:
        return safe_artifact_reference(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return path.name
