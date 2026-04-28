from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agent_harness import __version__
from agent_harness.cli import main
from agent_harness.operator import create_operator_app
from tests.conftest import seed_project


def _write_read_only_task(root: Path, task_id: str) -> Path:
    target = root / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": task_id,
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    return task_path


def _operator_headers(token: str = "operator-secret") -> dict[str, str]:
    return {"X-Agent-Harness-Operator-Token": token}


def test_operator_health_does_not_require_run_storage(tmp_path: Path) -> None:
    runs_dir = tmp_path / ".agent-harness" / "runs"
    assert not runs_dir.exists()

    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "operator_health.v1",
        "status": "ok",
        "agent_harness_version": __version__,
        "mode": "local_operator",
        "local_only": True,
    }
    assert not runs_dir.exists()


def test_operator_api_rejects_missing_token(tmp_path: Path) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get("/api/v1/runs")

    assert response.status_code == 401
    assert "operator token" in response.json()["detail"]
    assert "operator-secret" not in response.text


def test_operator_api_rejects_invalid_token_without_leaking_configured_token(
    tmp_path: Path,
) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/runs",
        headers={"X-Agent-Harness-Operator-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    assert "operator token" in response.json()["detail"]
    assert "operator-secret" not in response.text


def test_operator_api_accepts_valid_token_for_unimplemented_route(
    tmp_path: Path,
) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/not-yet-implemented",
        headers={"X-Agent-Harness-Operator-Token": "operator-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "operator API route not implemented"
    assert "operator-secret" not in response.text


def test_operator_run_detail_matches_cli_inspect_run(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-detail")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-detail")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    assert main(["inspect", "run", run_summary["run_id"]]) == 0
    cli_inspect = json.loads(capsys.readouterr().out)

    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_run_detail.v1"
    assert body["run_id"] == run_summary["run_id"]
    assert body["summary"]["status"] == cli_inspect["summary"]["status"]
    assert body["summary"]["approvals"] == cli_inspect["summary"]["approvals"]
    assert body["events"] == cli_inspect["events"]
    assert body["artifact_index"] == cli_inspect["artifact_index"]


def test_operator_run_list_reads_existing_run_storage(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-list")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-list")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/runs",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_run_list.v1"
    assert body["count"] == 1
    assert body["runs"] == [run_summary]


def test_operator_run_detail_includes_optional_evidence_seen_by_cli_inspect(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-optional-evidence")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-optional-evidence")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"]
    optional_artifacts = {
        "provider": ("provider.json", {"schema_version": "provider_record.v1"}),
        "provider_calls": ("provider_calls.json", {"schema_version": "provider_calls.v1"}),
        "provider_input": ("provider_input.json", {"schema_version": "provider_input.v1"}),
        "security_findings": (
            "security_findings.json",
            {"schema_version": "security_findings.v1"},
        ),
        "runtime_adapter": ("runtime_adapter.json", {"schema_version": "runtime_adapter.v1"}),
        "schema_versions": ("schema_versions.json", {"schema_version": "schema_versions.v1"}),
        "template_apply": ("template_apply.json", {"schema_version": "template_apply.v1"}),
        "git_commit": ("git_commit.json", {"schema_version": "git_commit.v1"}),
    }
    for relative, payload in optional_artifacts.values():
        (run_dir / relative).write_text(json.dumps(payload), encoding="utf-8")
    workspace_metadata = {"schema_version": "workspace_metadata.v1", "applied_templates": []}
    (tmp_path / ".agent-harness" / "workspace.json").write_text(
        json.dumps(workspace_metadata),
        encoding="utf-8",
    )
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["artifacts"]["workspace_metadata"] = ".agent-harness/workspace.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    assert main(["inspect", "run", run_summary["run_id"]]) == 0
    cli_inspect = json.loads(capsys.readouterr().out)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    for field in optional_artifacts:
        assert body[field] == cli_inspect[field]
    assert body["workspace_metadata"] == cli_inspect["workspace_metadata"]


def test_operator_run_detail_returns_not_found_for_missing_run(tmp_path: Path) -> None:
    seed_project(tmp_path)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/runs/run-does-not-exist",
        headers=_operator_headers(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"
    assert str(tmp_path) not in response.text


def test_operator_run_detail_reports_malformed_required_artifact_safely(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-malformed"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text("{not-json", encoding="utf-8")
    (run_dir / "artifact-index.json").write_text(
        json.dumps({"run_id": "run-malformed", "artifacts": {}}),
        encoding="utf-8",
    )
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/runs/run-malformed",
        headers=_operator_headers(),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "malformed run artifact: summary.json"
    assert str(tmp_path) not in response.text
