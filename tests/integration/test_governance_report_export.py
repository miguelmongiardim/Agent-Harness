from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_harness.cli import main


def test_governance_report_and_export_include_safe_provider_audit_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    workspace = _copy_provider_audit_workspace(tmp_path)
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-governance-provider-audit")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T19:00:00Z")
    monkeypatch.setenv(
        "AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT",
        "recorded://openai_compatible/read_only",
    )
    monkeypatch.setenv("AGENT_HARNESS_PROVIDER_AUDIT_API_KEY", "provider-audit-test-secret")

    assert main(["run", "task.json", "--auto-approve"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "completed"
    run_dir = workspace / ".agent-harness" / "runs" / "run-governance-provider-audit"
    raw_payload_text = "raw-provider-export-secret-should-not-appear"
    (run_dir / "raw_provider_payload.json").write_text(
        json.dumps(
            {
                "headers": {"authorization": "Bearer raw-provider-export-token"},
                "api_key": "sk-governance-export-key",
                "prompt": raw_payload_text,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert main(["governance", "report", "--format", "markdown"]) == 0
    markdown = capsys.readouterr().out
    for heading in (
        "## Policy",
        "## Runs",
        "## Approvals",
        "## Provider",
        "## Retrieval",
        "## Templates",
        "## Skills",
        "## MCP",
        "## Multi-Agent",
        "## Security",
        "## Release Readiness",
        "## Unsupported Claims",
    ):
        assert heading in markdown
    _assert_report_is_redaction_safe(markdown, tmp_path, raw_payload_text)

    assert main(["governance", "report", "--format", "json"]) == 0
    report_output = capsys.readouterr().out
    report = json.loads(report_output)
    assert report["schema_version"] == "governance_report.v1"
    assert report["summary"]["schema_version"] == "governance_summary.v1"
    assert report["check"]["schema_version"] == "governance_check.v1"
    assert any(finding["source"] == "raw_provider_payload" for finding in report["findings"])
    _assert_report_is_redaction_safe(report_output, tmp_path, raw_payload_text)

    export_dir = workspace / ".agent-harness" / "governance"
    assert main(["governance", "export", "--output", str(export_dir)]) == 0
    export_output = capsys.readouterr().out
    export_result = json.loads(export_output)

    expected_files = {
        "governance_summary.v1.json",
        "governance_report.v1.md",
        "governance_report.v1.json",
        "governance_index.v1.json",
        "governance_findings.v1.json",
    }
    assert {Path(path).name for path in export_result["files"]} == expected_files
    assert {path.name for path in export_dir.iterdir()} == expected_files

    exported_report = json.loads(
        (export_dir / "governance_report.v1.json").read_text(encoding="utf-8")
    )
    findings = json.loads((export_dir / "governance_findings.v1.json").read_text(encoding="utf-8"))
    index = json.loads((export_dir / "governance_index.v1.json").read_text(encoding="utf-8"))

    assert exported_report["schema_version"] == "governance_report.v1"
    assert findings["schema_version"] == "governance_findings.v1"
    assert all(
        finding["schema_version"] == "governance_finding.v1" for finding in findings["findings"]
    )
    assert index["schema_version"] == "governance_index.v1"
    assert index["entries"]

    required_index_keys = {
        "artifact_type",
        "path",
        "content_hash",
        "source_run_id",
        "schema_version",
        "redaction_status",
        "inclusion_status",
    }
    for entry in index["entries"]:
        assert required_index_keys <= set(entry)
        assert str(tmp_path) not in entry["path"]
        assert ".." not in Path(entry["path"]).parts

    assert any(
        entry["artifact_type"] == "run_summary"
        and entry["source_run_id"] == "run-governance-provider-audit"
        and entry["content_hash"]
        and entry["inclusion_status"] == "included"
        for entry in index["entries"]
    )
    assert any(
        entry["artifact_type"] == "raw_provider_payload"
        and entry["redaction_status"] == "excluded_raw"
        and entry["inclusion_status"] == "excluded"
        for entry in index["entries"]
    )
    assert not (export_dir / "raw_provider_payload.json").exists()

    combined_exports = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(export_dir.iterdir())
    )
    _assert_report_is_redaction_safe(combined_exports, tmp_path, raw_payload_text)


def _copy_provider_audit_workspace(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "examples" / "provider_audit"
    destination = tmp_path / "provider_audit"
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".agent-harness"))
    return destination


def _assert_report_is_redaction_safe(
    text: str,
    tmp_path: Path,
    raw_payload_text: str,
) -> None:
    assert str(tmp_path) not in text
    for leaked in (
        "provider-audit-test-secret",
        raw_payload_text,
        "raw-provider-export-token",
        "sk-governance-export-key",
        "authorization",
    ):
        assert leaked not in text
