from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_governance_check_blocks_raw_provider_payloads_and_unsafe_artifact_refs_without_leaking(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-governance-risk"
    run_dir.mkdir(parents=True)
    raw_payload = {
        "headers": {"authorization": "Bearer raw-secret-token"},
        "prompt": "raw prompt payload should not appear",
        "api_key": "sk-raw-provider-key",
        "env": "OPENAI_API_KEY=raw-env-value",
    }
    (run_dir / "raw_provider_payload.json").write_text(
        json.dumps(raw_payload, indent=2),
        encoding="utf-8",
    )
    absolute_reference = tmp_path / "absolute-provider-payload.json"
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "schema_version": "summary.v1",
                "run_id": "run-governance-risk",
                "task_id": "governance-risk",
                "status": "completed",
                "events_count": 3,
                "approvals": [],
                "artifacts": {
                    "summary": ".agent-harness/runs/run-governance-risk/summary.json",
                    "raw_provider_payload": (
                        ".agent-harness/runs/run-governance-risk/raw_provider_payload.json"
                    ),
                    "traversal": "../outside/provider.json",
                    "absolute": str(absolute_reference),
                },
                "started_at": "2026-04-30T18:00:00Z",
                "ended_at": "2026-04-30T18:01:00Z",
            }
        ),
        encoding="utf-8",
    )
    _write_docs_check_report(tmp_path)

    assert main(["governance", "check"]) == 1
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["schema_version"] == "governance_check.v1"
    assert result["status"] == "failed"
    assert result["exit_code"] == 1
    findings = result["findings"]
    blocking = [finding for finding in findings if finding["blocks_release"]]
    advisory = [finding for finding in findings if not finding["blocks_release"]]
    assert result["blocking_findings"] == len(blocking)
    assert result["advisory_findings"] == len(advisory)
    assert {finding["source"] for finding in blocking} >= {
        "raw_provider_payload",
        "unsafe_artifact_reference",
    }
    assert all(finding["severity"] == "critical" for finding in blocking)
    assert any(
        finding["source"] == "docs_check"
        and finding["domain"] == "docs"
        and finding["severity"] == "medium"
        for finding in advisory
    )
    assert all(finding["schema_version"] == "governance_finding.v1" for finding in findings)

    assert str(tmp_path) not in output
    assert str(absolute_reference) not in output
    for leaked in (
        "raw-secret-token",
        "raw prompt payload should not appear",
        "sk-raw-provider-key",
        "raw-env-value",
        "authorization",
        "OPENAI_API_KEY",
    ):
        assert leaked not in output


def test_governance_check_reports_advisory_findings_without_failing(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_docs_check_report(tmp_path)

    assert main(["governance", "check"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["schema_version"] == "governance_check.v1"
    assert result["status"] == "passed"
    assert result["exit_code"] == 0
    assert result["blocking_findings"] == 0
    assert result["advisory_findings"] == 1
    assert result["findings"][0]["source"] == "docs_check"
    assert result["findings"][0]["blocks_release"] is False


def test_governance_check_returns_exit_2_for_invalid_config_without_leaking_input(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    raw_config_secret = "raw-config-secret-should-not-appear"
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                f"project_name: {raw_config_secret}",
                "artifact_root: ../outside",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["governance", "check"]) == 2
    output = capsys.readouterr().out
    result = json.loads(output)

    assert result["schema_version"] == "governance_check.v1"
    assert result["status"] == "invalid"
    assert result["exit_code"] == 2
    assert result["findings"] == []
    assert result["diagnostics"] == [
        {
            "severity": "error",
            "domain": "governance",
            "message": "governance input, config, or artifact root is invalid",
            "artifact_reference": None,
        }
    ]
    assert raw_config_secret not in output
    assert str(tmp_path) not in output


def test_governance_check_returns_exit_3_for_internal_errors_without_leaking_exception(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    def fail_check(root: Path):  # type: ignore[no-untyped-def]
        del root
        raise RuntimeError("internal-secret-should-not-appear")

    monkeypatch.setattr("agent_harness.cli.run_governance_check", fail_check)

    assert main(["governance", "check"]) == 3
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert result["schema_version"] == "governance_check.v1"
    assert result["status"] == "internal_error"
    assert result["exit_code"] == 3
    assert result["findings"] == []
    assert result["diagnostics"] == [
        {
            "severity": "error",
            "domain": "governance",
            "message": "governance check failed with an internal error",
            "artifact_reference": None,
        }
    ]
    assert "internal-secret-should-not-appear" not in captured.out
    assert "internal-secret-should-not-appear" not in captured.err


def _write_docs_check_report(root: Path) -> None:
    docs_dir = root / ".agent-harness" / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "docs-check.json").write_text(
        json.dumps(
            {
                "schema_version": "docs_check.v1",
                "status": "failed",
                "findings": [
                    {
                        "rule_id": "unsupported_governance_scope_claim",
                        "path": "docs/governance.md",
                        "line": 5,
                        "message": "Docs claim unsupported v1.8.0 governance behavior as available",
                        "text": "Agent Harness provides hosted governance.",
                    }
                ],
                "counts": {"findings": 1},
            }
        ),
        encoding="utf-8",
    )
