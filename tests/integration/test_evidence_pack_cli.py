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
        and "agent-harness governance export --output .agent-harness/governance/" in diagnostic[
            "message"
        ]
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
    assert {
        diagnostic["artifact_reference"] for diagnostic in result["diagnostics"]
    } == {
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
        main(["evidence", "pack", "--output", ".agent-harness/evidence", "--format", "json"])
        == 0
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

    checksum_lines = (evidence_root / "checksums.sha256").read_text(
        encoding="utf-8"
    ).splitlines()
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


def _write_governance_exports(root: Path, *, missing_filename: str) -> None:
    governance_dir = root / ".agent-harness" / "governance"
    governance_dir.mkdir(parents=True)
    for filename, payload in GOVERNANCE_EXPORT_FIXTURES.items():
        if filename == missing_filename:
            continue
        (governance_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
