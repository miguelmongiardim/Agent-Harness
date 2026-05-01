from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.evidence.checks import REQUIRED_GOVERNANCE_EXPORTS
from agent_harness.evidence.schema import (
    EvidenceExportResult,
    EvidenceFindingCounts,
    EvidenceFindingsExport,
    EvidenceIndex,
    EvidenceIndexEntry,
    EvidenceManifest,
    EvidenceManifestFile,
    EvidencePack,
    EvidenceWorkspaceIdentity,
)
from agent_harness.utils import (
    hash_file,
    load_json,
    normalize_relative_path,
    now_utc,
    stable_id,
    write_json,
)

EvidencePackFormat = Literal["bundle", "json", "markdown"]


def build_evidence_pack(
    project_root: Path,
    *,
    output: Path,
    profile: str,
    format: EvidencePackFormat,
) -> EvidenceExportResult:
    del format
    root = project_root.resolve()
    config = load_config(root)
    artifact_root = normalize_relative_path(config.artifact_root)
    governance_dir = root / artifact_root / "governance"
    output_dir = output if output.is_absolute() else root / output
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = now_utc()
    governance_files = _governance_files(root, governance_dir)
    governance_hashes = {reference: hash_file(path) for reference, path, _ in governance_files}
    summary = load_json(governance_dir / "governance_summary.v1.json")
    findings = load_json(governance_dir / "governance_findings.v1.json")
    workspace = _workspace_identity(summary, artifact_root)
    pack_id = stable_id(
        "evidence-pack",
        __version__,
        profile,
        workspace.model_dump(mode="json"),
        governance_hashes,
        generated_at.isoformat(),
    )

    pack = EvidencePack(
        pack_id=pack_id,
        generated_at=generated_at,
        profile=profile,
        agent_harness_version=__version__,
        workspace=workspace,
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
        ],
    )
    findings_export = EvidenceFindingsExport(
        pack_id=pack_id,
        generated_at=generated_at,
        counts=EvidenceFindingCounts.model_validate(
            findings.get("counts", {"total": 0, "by_severity": {}})
        ),
        findings=[],
    )
    manifest = EvidenceManifest(
        pack_id=pack_id,
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
        ],
    )

    exported = {
        "evidence_pack.v1.json": pack.model_dump(mode="json"),
        "evidence_manifest.v1.json": manifest.model_dump(mode="json"),
        "evidence_index.v1.json": index.model_dump(mode="json"),
        "evidence_findings.v1.json": findings_export.model_dump(mode="json"),
    }
    export_order = [
        "evidence_pack.v1.json",
        "evidence_manifest.v1.json",
        "evidence_index.v1.json",
        "evidence_findings.v1.json",
    ]
    for filename, payload in exported.items():
        write_json(output_dir / filename, payload)
    _write_checksums(output_dir, sorted(export_order))

    files = [_display_path(root, output_dir / filename) for filename in export_order]
    files.append(_display_path(root, output_dir / "checksums.sha256"))
    return EvidenceExportResult(
        generated_at=generated_at,
        status="passed",
        exit_code=0,
        output_path=_display_path(root, output_dir),
        files=files,
    )


def _governance_files(root: Path, governance_dir: Path) -> list[tuple[str, Path, str]]:
    return [
        (_display_path(root, governance_dir / filename), governance_dir / filename, schema_version)
        for schema_version, filename in REQUIRED_GOVERNANCE_EXPORTS
    ]


def _workspace_identity(summary: object, artifact_root: str) -> EvidenceWorkspaceIdentity:
    workspace = summary.get("workspace", {}) if isinstance(summary, dict) else {}
    return EvidenceWorkspaceIdentity(
        project_name=str(workspace.get("project_name", "")),
        artifact_root=str(workspace.get("artifact_root", artifact_root)),
        config_path=str(workspace.get("config_path", "agent-harness.yaml")),
        default_policy=str(workspace.get("default_policy", "default")),
        policy_path=str(workspace.get("policy_path", "policies/default.json")),
    )


def _write_checksums(output_dir: Path, filenames: list[str]) -> None:
    lines = [f"{hash_file(output_dir / filename)}  {filename}" for filename in filenames]
    (output_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_path(root: Path, path: Path) -> str:
    try:
        return normalize_relative_path(path.resolve().relative_to(root).as_posix())
    except ValueError:
        return str(path)
