from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from agent_harness.evidence.schema import (
    EvidenceFindingsExport,
    EvidenceIndex,
    EvidenceManifest,
    EvidencePack,
)
from tests.conftest import seed_project

GOVERNANCE_EXPORT_FIXTURES = {
    "governance_summary.v1.json": {
        "schema_version": "governance_summary.v1",
        "workspace": {
            "project_name": "test-project",
            "artifact_root": ".agent-harness",
            "config_path": "agent-harness.yaml",
            "default_policy": "default",
            "policy_path": "policies/default.json",
        },
        "domains": {},
        "policy": {"default_profile": "default", "profiles": []},
        "runs": {},
    },
    "governance_report.v1.json": {
        "schema_version": "governance_report.v1",
        "summary": {
            "schema_version": "governance_summary.v1",
            "workspace": {
                "project_name": "test-project",
                "artifact_root": ".agent-harness",
                "config_path": "agent-harness.yaml",
                "default_policy": "default",
                "policy_path": "policies/default.json",
            },
            "domains": {},
            "policy": {"default_profile": "default", "profiles": []},
            "runs": {},
        },
        "check": {"schema_version": "governance_check.v1", "status": "passed", "exit_code": 0},
        "sections": [],
        "findings": [],
        "diagnostics": [],
    },
    "governance_index.v1.json": {
        "schema_version": "governance_index.v1",
        "entries": [],
    },
    "governance_findings.v1.json": {
        "schema_version": "governance_findings.v1",
        "counts": {"total": 0, "by_severity": {}},
        "findings": [],
    },
}


def test_evidence_help_exposes_pack_check_and_index_commands(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as exc:
        main(["evidence", "--help"])

    assert exc.value.code == 0

    help_text = capsys.readouterr().out
    assert "pack" in help_text
    assert "check" in help_text
    assert "index" in help_text


def test_evidence_pack_fails_when_v12_governance_exports_are_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["evidence", "pack", "--output", ".agent-harness/evidence"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["schema_version"] == "evidence_check.v1"
    assert result["status"] == "invalid"
    assert result["exit_code"] == 2
    assert [diagnostic["artifact_reference"] for diagnostic in result["diagnostics"]] == [
        ".agent-harness/governance/governance_summary.v1.json",
        ".agent-harness/governance/governance_report.v1.json",
        ".agent-harness/governance/governance_index.v1.json",
        ".agent-harness/governance/governance_findings.v1.json",
    ]
    assert all(
        diagnostic["severity"] == "error"
        and diagnostic["domain"] == "evidence"
        and "missing V12 governance export prerequisite" in diagnostic["message"]
        and "agent-harness governance export --output .agent-harness/governance/"
        in diagnostic["message"]
        for diagnostic in result["diagnostics"]
    )
    assert str(tmp_path) not in output
    assert not (tmp_path / ".agent-harness" / "evidence").exists()
    assert not (tmp_path / ".agent-harness" / "governance").exists()


def test_evidence_check_fails_when_v12_governance_exports_are_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["evidence", "check"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["schema_version"] == "evidence_check.v1"
    assert result["status"] == "invalid"
    assert result["exit_code"] == 2
    assert {diagnostic["artifact_reference"] for diagnostic in result["diagnostics"]} == {
        ".agent-harness/governance/governance_summary.v1.json",
        ".agent-harness/governance/governance_report.v1.json",
        ".agent-harness/governance/governance_index.v1.json",
        ".agent-harness/governance/governance_findings.v1.json",
    }
    assert str(tmp_path) not in output
    assert not (tmp_path / ".agent-harness" / "governance").exists()


@pytest.mark.parametrize(
    ("missing_filename", "missing_schema"),
    [
        ("governance_summary.v1.json", "governance_summary.v1"),
        ("governance_report.v1.json", "governance_report.v1"),
        ("governance_index.v1.json", "governance_index.v1"),
        ("governance_findings.v1.json", "governance_findings.v1"),
    ],
)
def test_evidence_pack_names_each_missing_v12_governance_export(
    tmp_path: Path,
    monkeypatch,
    capsys,
    missing_filename: str,
    missing_schema: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_governance_exports(tmp_path, missing_filename=missing_filename)

    assert main(["evidence", "pack"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["status"] == "invalid"
    assert result["exit_code"] == 2
    assert result["diagnostics"] == [
        {
            "severity": "error",
            "domain": "evidence",
            "message": (
                f"missing V12 governance export prerequisite: {missing_schema}; "
                "generate it first with `agent-harness governance export --output "
                ".agent-harness/governance/`"
            ),
            "artifact_reference": f".agent-harness/governance/{missing_filename}",
        }
    ]
    assert str(tmp_path) not in output


def test_evidence_pack_writes_minimal_canonical_json_from_v12_governance_exports(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-01-01T00:00:00Z")
    seed_project(tmp_path)
    _write_governance_exports(tmp_path, missing_filename="")

    assert (
        main(["evidence", "pack", "--output", ".agent-harness/evidence", "--format", "json"]) == 0
    )
    output = capsys.readouterr().out
    result = json.loads(output)
    evidence_root = tmp_path / ".agent-harness" / "evidence"

    assert result["schema_version"] == "evidence_export_result.v1"
    assert result["status"] == "passed"
    assert result["output_path"] == ".agent-harness/evidence"
    assert result["files"] == [
        ".agent-harness/evidence/evidence_pack.v1.json",
        ".agent-harness/evidence/evidence_manifest.v1.json",
        ".agent-harness/evidence/evidence_index.v1.json",
        ".agent-harness/evidence/evidence_findings.v1.json",
        ".agent-harness/evidence/checksums.sha256",
    ]

    pack = EvidencePack.model_validate_json(
        (evidence_root / "evidence_pack.v1.json").read_text(encoding="utf-8")
    )
    manifest = EvidenceManifest.model_validate_json(
        (evidence_root / "evidence_manifest.v1.json").read_text(encoding="utf-8")
    )
    index = EvidenceIndex.model_validate_json(
        (evidence_root / "evidence_index.v1.json").read_text(encoding="utf-8")
    )
    findings = EvidenceFindingsExport.model_validate_json(
        (evidence_root / "evidence_findings.v1.json").read_text(encoding="utf-8")
    )

    assert pack.pack_id
    assert pack.generated_at.isoformat() == "2026-01-01T00:00:00+00:00"
    assert pack.profile == "default"
    assert pack.workspace.project_name == "test-project"
    assert pack.governance_references == [
        ".agent-harness/governance/governance_summary.v1.json",
        ".agent-harness/governance/governance_report.v1.json",
        ".agent-harness/governance/governance_index.v1.json",
        ".agent-harness/governance/governance_findings.v1.json",
    ]
    assert "does not certify compliance" in pack.disclaimer
    assert pack.claim_status == "non_certifying"
    assert pack.redaction_status == "metadata_only"
    assert manifest.pack_id == pack.pack_id
    assert index.pack_id == pack.pack_id
    assert findings.pack_id == pack.pack_id
    assert not (evidence_root / "evidence_pack.v1.md").exists()
    assert not (evidence_root / "control_mapping.v1.md").exists()

    checksum_lines = (evidence_root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    checksum_paths = [line.split("  ", 1)[1] for line in checksum_lines]
    assert all(len(line.split("  ", 1)[0]) == 64 for line in checksum_lines)
    assert checksum_paths == sorted(checksum_paths)
    assert checksum_paths == [
        "evidence_findings.v1.json",
        "evidence_index.v1.json",
        "evidence_manifest.v1.json",
        "evidence_pack.v1.json",
    ]

    repeated_root = tmp_path / ".agent-harness" / "evidence-repeat"
    assert main(["evidence", "pack", "--output", str(repeated_root), "--format", "json"]) == 0
    capsys.readouterr()
    repeated_pack = json.loads(
        (repeated_root / "evidence_pack.v1.json").read_text(encoding="utf-8")
    )
    repeated_checksums = (repeated_root / "checksums.sha256").read_text(encoding="utf-8")
    assert repeated_pack["pack_id"] == pack.pack_id
    assert repeated_checksums == (evidence_root / "checksums.sha256").read_text(encoding="utf-8")


def test_evidence_pack_indexes_safe_artifacts_and_reports_unsafe_governance_refs(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-01-01T00:00:00Z")
    seed_project(tmp_path)
    _write_governance_exports(tmp_path, missing_filename="")

    run_dir = tmp_path / ".agent-harness" / "runs" / "run-safe-index"
    run_dir.mkdir(parents=True)
    safe_summary = run_dir / "summary.json"
    safe_summary.write_text(
        json.dumps(
            {
                "schema_version": "summary.v1",
                "run_id": "run-safe-index",
                "task_id": "safe-index",
                "status": "completed",
                "events_count": 1,
                "approvals": [],
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "raw_provider_payload.json").write_text(
        json.dumps(
            {
                "headers": {"authorization": "Bearer raw-secret-token"},
                "api_key": "sk-provider-payload-key",
                "prompt": "raw provider prompt must not appear",
            }
        ),
        encoding="utf-8",
    )
    absolute_payload = tmp_path / "absolute-provider-payload.json"
    absolute_payload.write_text(
        json.dumps({"api_key": "absolute-path-secret"}),
        encoding="utf-8",
    )
    _write_governance_index(
        tmp_path,
        [
            {
                "artifact_type": "run_summary",
                "path": ".agent-harness/runs/run-safe-index/summary.json",
                "content_hash": "stale-governance-hash",
                "source_run_id": "run-safe-index",
                "schema_version": "summary.v1",
                "redaction_status": "safe",
                "inclusion_status": "included",
            },
            {
                "artifact_type": "provider_calls",
                "path": str(absolute_payload),
                "content_hash": "unsafe-absolute-hash",
                "source_run_id": "run-safe-index",
                "schema_version": "provider_calls.v1",
                "redaction_status": "metadata_only",
                "inclusion_status": "included",
            },
            {
                "artifact_type": "context_manifest",
                "path": "../outside/context_manifest.json",
                "content_hash": "unsafe-traversal-hash",
                "source_run_id": "run-safe-index",
                "schema_version": "context_manifest.v2",
                "redaction_status": "redacted",
                "inclusion_status": "included",
            },
            {
                "artifact_type": "raw_provider_payload",
                "path": ".agent-harness/runs/run-safe-index/raw_provider_payload.json",
                "content_hash": "raw-payload-hash",
                "source_run_id": "run-safe-index",
                "schema_version": None,
                "redaction_status": "excluded_raw",
                "inclusion_status": "excluded",
            },
            {
                "artifact_type": "private_upload",
                "path": "sandbox:/mnt/data/customer-upload.txt",
                "content_hash": "private-upload-hash",
                "source_run_id": None,
                "schema_version": None,
                "redaction_status": "unknown",
                "inclusion_status": "included",
            },
        ],
    )

    assert (
        main(["evidence", "pack", "--output", ".agent-harness/evidence", "--format", "json"]) == 0
    )
    capsys.readouterr()

    evidence_root = tmp_path / ".agent-harness" / "evidence"
    index = json.loads((evidence_root / "evidence_index.v1.json").read_text(encoding="utf-8"))
    findings = json.loads((evidence_root / "evidence_findings.v1.json").read_text(encoding="utf-8"))
    serialized_pack = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(evidence_root.glob("*.json"))
    )

    safe_entries = [
        entry
        for entry in index["entries"]
        if entry["path"] == ".agent-harness/runs/run-safe-index/summary.json"
    ]
    assert safe_entries == [
        {
            "artifact_type": "run_summary",
            "content_hash": _sha256_file(safe_summary),
            "inclusion_status": "included",
            "path": ".agent-harness/runs/run-safe-index/summary.json",
            "redaction_status": "safe",
            "schema_version": "summary.v1",
        }
    ]
    assert all(not Path(entry["path"]).is_absolute() for entry in index["entries"])
    assert all(".." not in Path(entry["path"]).parts for entry in index["entries"])
    assert not any(entry["path"] == str(absolute_payload) for entry in index["entries"])
    assert not any(
        entry["path"] == "../outside/context_manifest.json" for entry in index["entries"]
    )
    assert not any("sandbox:/mnt/data" in entry["path"] for entry in index["entries"])

    finding_sources = {finding["source"] for finding in findings["findings"]}
    assert {
        "absolute_artifact_reference",
        "path_traversal_artifact_reference",
        "raw_provider_payload",
        "private_upload_reference",
    } <= finding_sources
    assert findings["counts"]["total"] == len(findings["findings"])
    assert findings["counts"]["by_severity"]["critical"] >= 4
    assert all(
        finding["severity"] == "critical"
        and finding["domain"] == "evidence"
        and finding["recommendation"]
        and finding["blocks_release"] is True
        and finding["blocks_evidence_pack"] is True
        and finding["omission_reason"]
        for finding in findings["findings"]
    )

    for leaked in (
        str(tmp_path),
        str(absolute_payload),
        "../outside/context_manifest.json",
        "sandbox:/mnt/data",
        "customer-upload.txt",
        "raw-secret-token",
        "sk-provider-payload-key",
        "raw provider prompt must not appear",
        "absolute-path-secret",
        "authorization",
    ):
        assert leaked not in serialized_pack


def test_evidence_pack_omits_credential_like_refs_and_raw_vector_db_internals(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-01-01T00:00:00Z")
    seed_project(tmp_path)
    _write_governance_exports(tmp_path, missing_filename="")

    credential_ref = ".agent-harness/runs/run-sensitive/OPENAI_API_KEY=env-secret-value.json"
    vector_ref = ".agent-harness/retrieval/qdrant/raw-collection-points.json"
    credential_path = tmp_path / credential_ref
    vector_path = tmp_path / vector_ref
    credential_path.parent.mkdir(parents=True)
    vector_path.parent.mkdir(parents=True)
    credential_path.write_text(
        json.dumps({"value": "env-secret-value"}),
        encoding="utf-8",
    )
    vector_path.write_text(
        json.dumps({"vector": [0.1, 0.2], "payload": "customer-vector-secret"}),
        encoding="utf-8",
    )
    _write_governance_index(
        tmp_path,
        [
            {
                "artifact_type": "provider_credential_env",
                "path": credential_ref,
                "content_hash": "credential-hash",
                "source_run_id": "run-sensitive",
                "schema_version": None,
                "redaction_status": "unknown",
                "inclusion_status": "included",
            },
            {
                "artifact_type": "qdrant_raw_collection",
                "path": vector_ref,
                "content_hash": "vector-hash",
                "source_run_id": None,
                "schema_version": None,
                "redaction_status": "unknown",
                "inclusion_status": "included",
            },
        ],
    )

    assert (
        main(["evidence", "pack", "--output", ".agent-harness/evidence", "--format", "json"]) == 0
    )
    capsys.readouterr()

    evidence_root = tmp_path / ".agent-harness" / "evidence"
    index = json.loads((evidence_root / "evidence_index.v1.json").read_text(encoding="utf-8"))
    findings = json.loads((evidence_root / "evidence_findings.v1.json").read_text(encoding="utf-8"))
    serialized_pack = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(evidence_root.glob("*.json"))
    )

    assert not any(entry["path"] == credential_ref for entry in index["entries"])
    assert not any(entry["path"] == vector_ref for entry in index["entries"])
    assert {
        "credential_like_artifact_reference",
        "raw_vector_db_internal",
    } <= {finding["source"] for finding in findings["findings"]}

    for leaked in (
        "OPENAI_API_KEY",
        "env-secret-value",
        "raw-collection-points.json",
        "customer-vector-secret",
    ):
        assert leaked not in serialized_pack


def test_evidence_pack_reports_absent_optional_domains_as_not_present(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-01-01T00:00:00Z")
    seed_project(tmp_path)
    _write_governance_exports(tmp_path, missing_filename="")

    assert (
        main(["evidence", "pack", "--output", ".agent-harness/evidence", "--format", "json"]) == 0
    )
    capsys.readouterr()

    pack = json.loads(
        (tmp_path / ".agent-harness" / "evidence" / "evidence_pack.v1.json").read_text(
            encoding="utf-8"
        )
    )

    for domain in (
        "provider",
        "retrieval",
        "templates",
        "skills",
        "mcp",
        "multi_agent",
        "supply_chain",
        "release_readiness",
    ):
        assert pack["domains"][domain] == {
            "status": "not_present",
            "message": f"{domain} evidence not present in V12 governance exports",
            "evidence_refs": [],
        }


def _write_governance_exports(root: Path, *, missing_filename: str) -> None:
    governance_dir = root / ".agent-harness" / "governance"
    governance_dir.mkdir(parents=True)
    for filename, payload in GOVERNANCE_EXPORT_FIXTURES.items():
        if filename == missing_filename:
            continue
        (governance_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def _write_governance_index(root: Path, entries: list[dict[str, object]]) -> None:
    (root / ".agent-harness" / "governance" / "governance_index.v1.json").write_text(
        json.dumps({"schema_version": "governance_index.v1", "entries": entries}),
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
