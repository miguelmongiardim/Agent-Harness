from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Literal

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.evidence.checks import REQUIRED_GOVERNANCE_EXPORTS
from agent_harness.evidence.schema import (
    ControlMapping,
    ControlMappingEntry,
    EvidenceControlCoverageStatus,
    EvidenceDomainStatus,
    EvidenceDomainSummary,
    EvidenceExportResult,
    EvidenceFinding,
    EvidenceFindingCounts,
    EvidenceFindingSeverity,
    EvidenceFindingsExport,
    EvidenceIndex,
    EvidenceIndexEntry,
    EvidenceManifest,
    EvidenceManifestFile,
    EvidencePack,
    EvidenceRedactionStatus,
    EvidenceWorkspaceIdentity,
)
from agent_harness.utils import (
    canonical_json,
    hash_file,
    load_json,
    normalize_relative_path,
    now_utc,
    stable_id,
    write_json,
)

EvidencePackFormat = Literal["bundle", "json", "markdown"]


@dataclass(frozen=True)
class EvidencePackState:
    generated_at: datetime
    pack: EvidencePack
    index: EvidenceIndex
    findings_export: EvidenceFindingsExport
    control_mapping: ControlMapping


CONTROL_MAPPING_LIMITATIONS = [
    "This mapping is review only and is generated from packaged evidence references.",
    "Coverage statuses describe available evidence, not control effectiveness or audit results.",
    "Formal certification, legal determinations, and framework conformance remain out of scope.",
]
CONTROL_THEME_DEFINITIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ai_risk_governance", "AI Risk Governance", ("governance", "multi_agent")),
    (
        "secure_software_development",
        "Secure Software Development",
        ("security", "policy", "supply_chain"),
    ),
    ("data_classification", "Data Classification", ("policy", "provider", "retrieval")),
    ("provider_governance", "Provider Governance", ("provider",)),
    ("approval_governance", "Approval Governance", ("approvals",)),
    ("retrieval_provenance", "Retrieval Provenance", ("retrieval",)),
    ("supply_chain_evidence", "Supply Chain Evidence", ("supply_chain",)),
    ("documentation_claim_control", "Documentation Claim Control", ("docs_claim",)),
    ("release_readiness", "Release Readiness", ("release_readiness",)),
)
EVIDENCE_DOMAINS = (
    "governance",
    "policy",
    "approvals",
    "provider",
    "retrieval",
    "templates",
    "skills",
    "mcp",
    "multi_agent",
    "supply_chain",
    "security",
    "docs_claim",
    "release_readiness",
)
_PRIVATE_UPLOAD_REFERENCE = re.compile(
    r"(?i)(?:/mnt/data/|sandbox:/mnt/data|uploaded file|file-[A-Za-z0-9]{8,})"
)
_CREDENTIAL_LIKE_REFERENCE = re.compile(
    r"(?i)(?:[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*[:=]|"
    r"sk-(?:live|test)-|OPENAI_API_KEY|ANTHROPIC_API_KEY)"
)
_RAW_VECTOR_DB_REFERENCE = re.compile(
    r"(?i)(?:qdrant.*(?:raw|collection|point|snapshot|storage)|"
    r"(?:raw|vector)[-_]?(?:vector|embedding|db|database|collection|point))"
)


def build_evidence_pack(
    project_root: Path,
    *,
    output: Path,
    profile: str,
    format: EvidencePackFormat,
    archive: bool = False,
) -> EvidenceExportResult:
    root = project_root.resolve()
    output_dir = output if output.is_absolute() else root / output
    output_dir.mkdir(parents=True, exist_ok=True)

    state = build_evidence_state(root, profile=profile)
    generated_at = state.generated_at
    pack = state.pack
    index = state.index
    findings_export = state.findings_export
    control_mapping = state.control_mapping
    include_markdown = format in {"bundle", "markdown"}
    manifest = EvidenceManifest(
        pack_id=pack.pack_id,
        generated_at=generated_at,
        files=[
            EvidenceManifestFile(path="evidence_pack.v1.json", schema_version=pack.schema_version),
            EvidenceManifestFile(
                path="evidence_manifest.v1.json",
                schema_version="evidence_manifest.v1",
            ),
            EvidenceManifestFile(
                path="evidence_index.v1.json",
                schema_version=index.schema_version,
            ),
            EvidenceManifestFile(
                path="evidence_findings.v1.json",
                schema_version=findings_export.schema_version,
            ),
            EvidenceManifestFile(
                path="control_mapping.v1.json",
                schema_version=control_mapping.schema_version,
            ),
        ],
    )
    if include_markdown:
        manifest.files.append(
            EvidenceManifestFile(path="evidence_pack.v1.md", schema_version=pack.schema_version)
        )
        manifest.files.append(
            EvidenceManifestFile(
                path="control_mapping.v1.md",
                schema_version=control_mapping.schema_version,
            )
        )

    exported: dict[str, object] = {
        "evidence_pack.v1.json": pack.model_dump(mode="json"),
        "evidence_manifest.v1.json": manifest.model_dump(mode="json"),
        "evidence_index.v1.json": index.model_dump(mode="json"),
        "evidence_findings.v1.json": findings_export.model_dump(mode="json"),
        "control_mapping.v1.json": control_mapping.model_dump(mode="json"),
    }
    export_order = [
        "evidence_pack.v1.json",
        "evidence_manifest.v1.json",
        "evidence_index.v1.json",
        "evidence_findings.v1.json",
        "control_mapping.v1.json",
    ]
    if include_markdown:
        exported["evidence_pack.v1.md"] = _render_evidence_pack_markdown(
            pack,
            findings_export,
        )
        exported["control_mapping.v1.md"] = _render_control_mapping_markdown(control_mapping)
        export_order.append("evidence_pack.v1.md")
        export_order.append("control_mapping.v1.md")
    for filename, payload in exported.items():
        if filename.endswith(".json"):
            write_json(output_dir / filename, payload)
        else:
            (output_dir / filename).write_text(str(payload), encoding="utf-8")
    _write_checksums(output_dir, sorted(export_order))

    files = [_display_path(root, output_dir / filename) for filename in export_order]
    files.append(_display_path(root, output_dir / "checksums.sha256"))
    if archive:
        archive_path = _write_archive(output_dir, generated_at, sorted(export_order))
        files.append(_display_path(root, archive_path))
    return EvidenceExportResult(
        generated_at=generated_at,
        status="passed",
        exit_code=0,
        output_path=_display_path(root, output_dir),
        files=files,
    )


def build_evidence_state(project_root: Path, *, profile: str) -> EvidencePackState:
    root = project_root.resolve()
    config = load_config(root)
    artifact_root = normalize_relative_path(config.artifact_root)
    governance_dir = root / artifact_root / "governance"
    generated_at = now_utc()
    governance_files = _governance_files(root, governance_dir)
    governance_hashes = {reference: hash_file(path) for reference, path, _ in governance_files}
    summary = load_json(governance_dir / "governance_summary.v1.json")
    governance_index = load_json(governance_dir / "governance_index.v1.json")
    workspace = _workspace_identity(summary, artifact_root)
    pack_id = stable_id(
        "evidence-pack",
        __version__,
        profile,
        workspace.model_dump(mode="json"),
        governance_hashes,
        generated_at.isoformat(),
    )
    source_index_entries, evidence_findings = _source_index_entries(
        root,
        governance_index,
        _display_path(root, governance_dir / "governance_index.v1.json"),
    )
    domain_summaries, domain_findings = _domain_summaries(
        root,
        summary,
        _display_path(root, governance_dir / "governance_summary.v1.json"),
    )
    evidence_findings.extend(domain_findings)
    pack = EvidencePack(
        pack_id=pack_id,
        generated_at=generated_at,
        profile=profile,
        agent_harness_version=__version__,
        workspace=workspace,
        domains=domain_summaries,
        governance_references=list(governance_hashes),
        governance_hashes=governance_hashes,
    )
    index = EvidenceIndex(
        pack_id=pack_id,
        generated_at=generated_at,
        entries=[
            EvidenceIndexEntry(
                artifact_type=schema_version,
                path=reference,
                content_hash=governance_hashes[reference],
                schema_version=schema_version,
                redaction_status="metadata_only",
                inclusion_status="included",
            )
            for reference, _, schema_version in governance_files
        ]
        + source_index_entries,
    )
    findings_export = EvidenceFindingsExport(
        pack_id=pack_id,
        generated_at=generated_at,
        counts=_finding_counts(evidence_findings),
        findings=evidence_findings,
    )
    return EvidencePackState(
        generated_at=generated_at,
        pack=pack,
        index=index,
        findings_export=findings_export,
        control_mapping=_control_mapping(pack, index),
    )


def _write_archive(output_dir: Path, generated_at: datetime, filenames: list[str]) -> Path:
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_dir / f"agent-harness-evidence-pack-{timestamp}.zip"
    archive_names = sorted(filenames + ["checksums.sha256"])
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in archive_names:
            archive.write(output_dir / filename, arcname=filename)
    return archive_path


def _control_mapping(pack: EvidencePack, index: EvidenceIndex) -> ControlMapping:
    included_refs = {
        entry.path for entry in index.entries if entry.inclusion_status == "included"
    } | set(pack.governance_references)
    mappings: list[ControlMappingEntry] = []
    for theme_id, title, source_domains in CONTROL_THEME_DEFINITIONS:
        domain_summaries = [pack.domains[domain] for domain in source_domains]
        evidence_refs = sorted(
            {
                ref
                for summary in domain_summaries
                for ref in summary.evidence_refs
                if ref in included_refs
            }
        )
        coverage_status = _control_mapping_coverage(domain_summaries, evidence_refs)
        mappings.append(
            ControlMappingEntry(
                theme_id=theme_id,
                title=title,
                coverage_status=coverage_status,
                source_domains=list(source_domains),
                evidence_refs=evidence_refs,
                summary=_control_mapping_summary(title, coverage_status, source_domains),
                limitations=[
                    "Mapped evidence is suitable for review framing only.",
                    (
                        "The mapping does not assert control effectiveness, "
                        "audit pass/fail status, or certification."
                    ),
                ],
            )
        )
    return ControlMapping(
        pack_id=pack.pack_id,
        generated_at=pack.generated_at,
        limitations=CONTROL_MAPPING_LIMITATIONS,
        mappings=mappings,
    )


def _control_mapping_coverage(
    domain_summaries: list[EvidenceDomainSummary],
    evidence_refs: list[str],
) -> EvidenceControlCoverageStatus:
    statuses = [summary.status for summary in domain_summaries]
    if statuses and all(status == "roadmap_only" for status in statuses):
        return "roadmap_only"
    if not statuses or all(status == "not_present" for status in statuses):
        return "not_covered"
    if not evidence_refs:
        return "partially_covered"
    if all(status == "present" for status in statuses):
        return "covered"
    return "partially_covered"


def _control_mapping_summary(
    title: str,
    coverage_status: EvidenceControlCoverageStatus,
    source_domains: tuple[str, ...],
) -> str:
    domains = ", ".join(source_domains)
    return (
        f"{title} is {coverage_status.replace('_', ' ')} for review based on "
        f"the packaged {domains} evidence domains."
    )


def _render_control_mapping_markdown(mapping: ControlMapping) -> str:
    lines = [
        "# Control Mapping",
        "",
        mapping.disclaimer,
        "",
        "## Limitations",
        "",
    ]
    for limitation in mapping.limitations:
        lines.append(f"- {limitation}")
    lines.extend(["", "## Review Themes", ""])
    for entry in mapping.mappings:
        lines.extend(
            [
                f"### {entry.title}",
                "",
                f"- Theme id: `{entry.theme_id}`",
                f"- Coverage status: `{entry.coverage_status}`",
                "- Source domains: "
                + ", ".join(f"`{domain}`" for domain in entry.source_domains),
                f"- Summary: {entry.summary}",
                "- Evidence refs:",
            ]
        )
        if entry.evidence_refs:
            lines.extend(f"  - `{ref}`" for ref in entry.evidence_refs)
        else:
            lines.append("  - None")
        lines.append("- Limitations:")
        lines.extend(f"  - {limitation}" for limitation in entry.limitations)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_evidence_pack_markdown(
    pack: EvidencePack,
    findings_export: EvidenceFindingsExport,
) -> str:
    lines = [
        "# Evidence Pack",
        "",
        pack.disclaimer,
        "",
        "## Summary",
        "",
        f"- Pack id: `{pack.pack_id}`",
        f"- Generated at: `{pack.generated_at.isoformat()}`",
        f"- Profile: `{pack.profile}`",
        f"- Agent Harness version: `{pack.agent_harness_version}`",
        f"- Claim status: `{pack.claim_status}`",
        f"- Redaction status: `{pack.redaction_status}`",
        "",
        "## Workspace",
        "",
        f"- Project name: `{pack.workspace.project_name}`",
        f"- Artifact root: `{pack.workspace.artifact_root}`",
        f"- Config path: `{pack.workspace.config_path}`",
        f"- Default policy: `{pack.workspace.default_policy}`",
        f"- Policy path: `{pack.workspace.policy_path}`",
        "",
        "## Governance References",
        "",
    ]
    lines.extend(f"- `{reference}`" for reference in pack.governance_references)
    lines.extend(["", "## Domains", ""])
    for domain, summary in sorted(pack.domains.items()):
        lines.extend(
            [
                f"### {domain}",
                "",
                f"- Status: `{summary.status}`",
                f"- Message: {summary.message or 'No message'}",
                "- Evidence refs:",
            ]
        )
        if summary.evidence_refs:
            lines.extend(f"  - `{ref}`" for ref in summary.evidence_refs)
        else:
            lines.append("  - None")
        lines.append("- Summary:")
        if summary.summary:
            lines.extend(
                f"  - `{key}`: `{canonical_json(value)}`"
                for key, value in sorted(summary.summary.items())
            )
        else:
            lines.append("  - None")
        lines.append("")
    lines.extend(
        [
            "## Findings",
            "",
            f"- Total findings: `{findings_export.counts.total}`",
        ]
    )
    if findings_export.counts.by_severity:
        for severity, count in sorted(findings_export.counts.by_severity.items()):
            lines.append(f"- {severity}: `{count}`")
    else:
        lines.append("- Blocking findings: `0`")
    return "\n".join(lines).rstrip() + "\n"


def _governance_files(root: Path, governance_dir: Path) -> list[tuple[str, Path, str]]:
    return [
        (_display_path(root, governance_dir / filename), governance_dir / filename, schema_version)
        for schema_version, filename in REQUIRED_GOVERNANCE_EXPORTS
    ]


def _source_index_entries(
    root: Path,
    governance_index: object,
    governance_index_reference: str,
) -> tuple[list[EvidenceIndexEntry], list[EvidenceFinding]]:
    if not isinstance(governance_index, dict):
        return (
            [],
            [
                _finding(
                    source="malformed_governance_index",
                    message="Governance index is malformed and cannot be packaged safely.",
                    artifact_reference=governance_index_reference,
                    omission_reason="malformed_governance_index",
                    recommendation="Regenerate V12 governance exports before packaging evidence.",
                )
            ],
        )
    raw_entries = governance_index.get("entries", [])
    if not isinstance(raw_entries, list):
        return (
            [],
            [
                _finding(
                    source="malformed_governance_index",
                    message="Governance index entries are malformed and cannot be packaged safely.",
                    artifact_reference=governance_index_reference,
                    omission_reason="malformed_governance_index",
                    recommendation="Regenerate V12 governance exports before packaging evidence.",
                )
            ],
        )

    entries: list[EvidenceIndexEntry] = []
    findings: list[EvidenceFinding] = []
    seen_paths: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            findings.append(
                _finding(
                    source="malformed_governance_index_entry",
                    message="Governance index entry is malformed and was omitted.",
                    artifact_reference=governance_index_reference,
                    omission_reason="malformed_governance_index_entry",
                    recommendation="Regenerate V12 governance exports before packaging evidence.",
                )
            )
            continue
        entry, finding = _source_index_entry(root, raw_entry, governance_index_reference)
        if finding is not None:
            findings.append(finding)
            continue
        if entry is None or entry.path in seen_paths:
            continue
        seen_paths.add(entry.path)
        entries.append(entry)
    return sorted(entries, key=lambda entry: (entry.path, entry.artifact_type)), findings


def _source_index_entry(
    root: Path,
    raw_entry: dict[object, object],
    governance_index_reference: str,
) -> tuple[EvidenceIndexEntry | None, EvidenceFinding | None]:
    artifact_type = _safe_string(raw_entry.get("artifact_type"), "unknown")
    reference = raw_entry.get("path")
    if not isinstance(reference, str) or not reference.strip():
        return None, _finding(
            source="malformed_artifact_reference",
            message="Governance index entry does not contain a usable artifact reference.",
            artifact_reference=governance_index_reference,
            omission_reason="malformed_artifact_reference",
            recommendation="Regenerate V12 governance exports with normalized artifact references.",
        )
    if _is_private_upload_reference(reference):
        return None, _finding(
            source="private_upload_reference",
            message="Private uploaded-file artifact reference was omitted from the evidence pack.",
            artifact_reference=governance_index_reference,
            omission_reason="private_upload_reference",
            recommendation="Replace private upload references with safe project-relative evidence.",
        )
    if _is_credential_like_reference(raw_entry, reference):
        return None, _finding(
            source="credential_like_artifact_reference",
            message="Credential-like artifact reference was omitted from the evidence pack.",
            artifact_reference=governance_index_reference,
            omission_reason="credential_like_artifact_reference",
            recommendation="Replace credential-like references with metadata-only evidence.",
        )
    if _is_raw_vector_db_reference(raw_entry, reference):
        return None, _finding(
            source="raw_vector_db_internal",
            message="Raw vector database internal artifact was omitted from the evidence pack.",
            artifact_reference=governance_index_reference,
            omission_reason="raw_vector_db_internal",
            recommendation="Retain retrieval provenance summaries instead of raw vector internals.",
        )
    if _is_raw_provider_payload(raw_entry):
        return None, _finding(
            source="raw_provider_payload",
            message="Raw provider payload artifact was omitted from the evidence pack.",
            artifact_reference=_safe_artifact_reference(root, reference)
            or governance_index_reference,
            omission_reason="raw_provider_payload",
            recommendation="Retain redacted provider evidence instead of raw provider payloads.",
        )

    normalized = _safe_artifact_reference(root, reference)
    if normalized is None:
        source = (
            "absolute_artifact_reference"
            if _is_absolute_reference(reference)
            else "path_traversal_artifact_reference"
        )
        reason = "absolute_path" if source == "absolute_artifact_reference" else "path_traversal"
        return None, _finding(
            source=source,
            message="Unsafe artifact reference was omitted from the evidence pack.",
            artifact_reference=governance_index_reference,
            omission_reason=reason,
            recommendation="Regenerate governance exports with normalized project-relative paths.",
        )

    path = root / normalized
    if not path.exists() or not path.is_file():
        return None, _finding(
            source="missing_artifact_reference",
            message="Referenced artifact was absent and was omitted from the evidence pack.",
            artifact_reference=normalized,
            omission_reason="missing_artifact",
            recommendation="Regenerate governance exports after producing the referenced artifact.",
        )

    return (
        EvidenceIndexEntry(
            artifact_type=artifact_type,
            path=normalized,
            content_hash=hash_file(path),
            schema_version=_optional_string(raw_entry.get("schema_version")),
            redaction_status=_redaction_status(raw_entry.get("redaction_status")),
            inclusion_status="included",
        ),
        None,
    )


def _is_raw_provider_payload(raw_entry: dict[object, object]) -> bool:
    return (
        raw_entry.get("artifact_type") == "raw_provider_payload"
        or raw_entry.get("redaction_status") == "excluded_raw"
        or raw_entry.get("inclusion_status") == "excluded"
        and "provider" in _safe_string(raw_entry.get("artifact_type"), "")
    )


def _is_private_upload_reference(reference: str) -> bool:
    return bool(_PRIVATE_UPLOAD_REFERENCE.search(reference))


def _is_credential_like_reference(raw_entry: dict[object, object], reference: str) -> bool:
    artifact_type = _safe_string(raw_entry.get("artifact_type"), "")
    return bool(_CREDENTIAL_LIKE_REFERENCE.search(reference)) or "credential" in artifact_type


def _is_raw_vector_db_reference(raw_entry: dict[object, object], reference: str) -> bool:
    artifact_type = _safe_string(raw_entry.get("artifact_type"), "")
    return bool(_RAW_VECTOR_DB_REFERENCE.search(artifact_type)) or bool(
        _RAW_VECTOR_DB_REFERENCE.search(reference)
    )


def _safe_artifact_reference(root: Path, reference: str) -> str | None:
    try:
        if _is_absolute_reference(reference):
            return None
        normalized = normalize_relative_path(reference)
        (root / normalized).resolve().relative_to(root)
    except ValueError:
        return None
    return normalized


def _is_absolute_reference(reference: str) -> bool:
    return PureWindowsPath(reference).is_absolute() or reference.startswith("/")


def _safe_string(value: object, fallback: str) -> str:
    return value if isinstance(value, str) and value else fallback


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _redaction_status(value: object) -> EvidenceRedactionStatus:
    if value in {"safe", "redacted", "metadata_only", "excluded_raw", "unknown"}:
        return value  # type: ignore[return-value]
    return "unknown"


def _finding(
    *,
    source: str,
    message: str,
    artifact_reference: str | None,
    omission_reason: str,
    recommendation: str,
    severity: EvidenceFindingSeverity = "critical",
    domain: str = "evidence",
    blocks_release: bool = True,
    blocks_evidence_pack: bool = True,
) -> EvidenceFinding:
    evidence_refs = [artifact_reference] if artifact_reference else []
    return EvidenceFinding(
        finding_id=stable_id(
            "evidence",
            domain,
            source,
            severity,
            artifact_reference or "",
            omission_reason,
        ),
        severity=severity,
        domain=domain,
        source=source,
        message=message,
        artifact_reference=artifact_reference,
        evidence_refs=evidence_refs,
        omission_reason=omission_reason,
        recommendation=recommendation,
        blocks_release=blocks_release,
        blocks_evidence_pack=blocks_evidence_pack,
    )


def _finding_counts(findings: list[EvidenceFinding]) -> EvidenceFindingCounts:
    counts: dict[EvidenceFindingSeverity, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return EvidenceFindingCounts(total=len(findings), by_severity=counts)


def _workspace_identity(summary: object, artifact_root: str) -> EvidenceWorkspaceIdentity:
    workspace = summary.get("workspace", {}) if isinstance(summary, dict) else {}
    return EvidenceWorkspaceIdentity(
        project_name=str(workspace.get("project_name", "")),
        artifact_root=str(workspace.get("artifact_root", artifact_root)),
        config_path=str(workspace.get("config_path", "agent-harness.yaml")),
        default_policy=str(workspace.get("default_policy", "default")),
        policy_path=str(workspace.get("policy_path", "policies/default.json")),
    )


def _domain_summaries(
    root: Path,
    summary: object,
    governance_summary_reference: str,
) -> tuple[dict[str, EvidenceDomainSummary], list[EvidenceFinding]]:
    raw_domains = summary.get("domains", {}) if isinstance(summary, dict) else {}
    domains = raw_domains if isinstance(raw_domains, dict) else {}
    result: dict[str, EvidenceDomainSummary] = {}
    findings: list[EvidenceFinding] = []
    for domain in EVIDENCE_DOMAINS:
        raw_domain = domains.get(domain)
        if not isinstance(raw_domain, dict):
            result[domain] = EvidenceDomainSummary(
                status="not_present",
                message=f"{domain} evidence not present in V12 governance exports",
            )
            continue
        status = _domain_status(raw_domain.get("status"))
        domain_summary, summary_finding = _safe_domain_summary(
            raw_domain.get("summary"),
            domain=domain,
            governance_summary_reference=governance_summary_reference,
        )
        if summary_finding is not None:
            findings.append(summary_finding)
            status = "malformed_evidence"
        result[domain] = EvidenceDomainSummary(
            status=status,
            message=_safe_string(raw_domain.get("message"), ""),
            evidence_refs=_safe_evidence_refs(root, raw_domain.get("evidence_refs")),
            summary=domain_summary,
        )
    return result, findings


def _safe_domain_summary(
    value: object,
    *,
    domain: str,
    governance_summary_reference: str,
) -> tuple[dict[str, object], EvidenceFinding | None]:
    if value is None:
        return {}, None
    if not isinstance(value, dict):
        return {}, _finding(
            source="malformed_domain_summary",
            message="Governance domain summary is malformed and was omitted.",
            artifact_reference=governance_summary_reference,
            omission_reason="malformed_domain_summary",
            recommendation="Regenerate V12 governance summary domain metadata.",
            severity="high",
            domain=domain,
        )
    return _safe_domain_summary_mapping(value), None


def _safe_domain_summary_mapping(value: dict[object, object]) -> dict[str, object]:
    return {
        key: _safe_domain_summary_value(raw_value)
        for key, raw_value in sorted(value.items(), key=lambda item: str(item[0]))
        if isinstance(key, str) and key
    }


def _safe_domain_summary_value(value: object) -> object:
    if isinstance(value, str):
        return "[redacted]" if _is_unsafe_summary_string(value) else value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, list):
        return [_safe_domain_summary_value(item) for item in value]
    if isinstance(value, dict):
        return _safe_domain_summary_mapping(value)
    return str(value)


def _is_unsafe_summary_string(value: str) -> bool:
    if _is_private_upload_reference(value):
        return True
    if _CREDENTIAL_LIKE_REFERENCE.search(value):
        return True
    if _RAW_VECTOR_DB_REFERENCE.search(value):
        return True
    return _is_absolute_reference(value)


def _domain_status(value: object) -> EvidenceDomainStatus:
    if value in {
        "present",
        "not_present",
        "missing_evidence",
        "malformed_evidence",
        "blocked_by_policy",
        "roadmap_only",
    }:
        return value  # type: ignore[return-value]
    return "malformed_evidence"


def _safe_evidence_refs(root: Path, value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = _safe_artifact_reference(root, item)
        if normalized is not None:
            refs.append(normalized)
    return sorted(set(refs))


def _write_checksums(output_dir: Path, filenames: list[str]) -> None:
    lines = [f"{hash_file(output_dir / filename)}  {filename}" for filename in filenames]
    (output_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_path(root: Path, path: Path) -> str:
    try:
        return normalize_relative_path(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return str(path)
