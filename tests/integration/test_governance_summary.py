from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from tests.conftest import seed_project


def test_governance_help_exposes_summary_command(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as exc:
        main(["governance", "--help"])

    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "summary" in help_text


def test_governance_summary_reports_policy_runs_and_absent_optional_domains(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    target = tmp_path / "sample.py"
    raw_file_content = "RAW_VALUE = 'raw-token-should-not-appear'\n"
    target.write_text(raw_file_content, encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "governance-summary",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-governance-summary")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T18:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()

    assert main(["governance", "summary"]) == 0
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert summary["schema_version"] == "governance_summary.v1"
    assert summary["workspace"] == {
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "config_path": "agent-harness.yaml",
        "default_policy": "default",
        "policy_path": "policies/default.json",
    }
    assert summary["domains"]["policy"]["status"] == "present"
    assert summary["domains"]["runs"]["status"] == "present"
    for optional_domain in (
        "approvals",
        "provider",
        "retrieval",
        "templates",
        "skills",
        "mcp",
        "multi_agent",
        "security",
        "release_readiness",
    ):
        assert summary["domains"][optional_domain]["status"] == "not_present"

    assert summary["policy"] == {
        "default_profile": "default",
        "profiles": [
            {
                "name": "default",
                "schema_version": "policy.v2",
                "path": "policies/default.json",
            }
        ],
    }
    assert summary["runs"]["total"] == 1
    assert summary["runs"]["status_counts"]["dry_run"] == 1
    assert summary["runs"]["latest_run_id"] == "run-governance-summary"
    assert (
        summary["runs"]["latest_run_artifact"]
        == ".agent-harness/runs/run-governance-summary/summary.json"
    )
    assert summary["finding_counts"] == {"total": 0, "by_severity": {}}
    assert summary["findings"] == []
    assert summary["diagnostics"] == []
    assert str(tmp_path) not in output
    assert raw_file_content.strip() not in output


def test_governance_summary_reports_malformed_run_evidence_without_leaking_contents(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-malformed-summary"
    run_dir.mkdir(parents=True)
    raw_summary_content = "raw-summary-secret-should-not-appear"
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "summary.v1",
                "run_id": "run-malformed-summary",
                "task_id": "malformed-summary",
                "status": "dry_run",
                "events_count": raw_summary_content,
                "approvals": [],
                "artifacts": {},
                "started_at": "2026-04-30T18:00:00Z",
                "ended_at": "2026-04-30T18:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    assert main(["governance", "summary"]) == 0
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert summary["domains"]["runs"]["status"] == "malformed_evidence"
    assert summary["runs"]["total"] == 0
    assert summary["diagnostics"] == [
        {
            "severity": "error",
            "domain": "runs",
            "message": "run summary evidence is malformed",
            "artifact_reference": ".agent-harness/runs/run-malformed-summary/summary.json",
        }
    ]
    assert summary["finding_counts"] == {"total": 1, "by_severity": {"medium": 1}}
    assert summary["findings"][0]["source"] == "malformed_evidence"
    assert (
        summary["findings"][0]["artifact_reference"]
        == ".agent-harness/runs/run-malformed-summary/summary.json"
    )
    assert str(tmp_path) not in output
    assert raw_summary_content not in output


def test_governance_summary_reports_missing_policy_evidence_without_crashing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    (tmp_path / "policies" / "default.json").unlink()

    assert main(["governance", "summary"]) == 0
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert summary["domains"]["policy"]["status"] == "missing_evidence"
    assert summary["policy"] == {"default_profile": "default", "profiles": []}
    assert summary["diagnostics"] == [
        {
            "severity": "error",
            "domain": "policy",
            "message": "policy profile not found: default",
            "artifact_reference": "policies/default.json",
        }
    ]
    assert summary["finding_counts"] == {"total": 1, "by_severity": {"medium": 1}}
    assert summary["findings"][0]["source"] == "missing_evidence"
    assert summary["findings"][0]["artifact_reference"] == "policies/default.json"
    assert str(tmp_path) not in output
