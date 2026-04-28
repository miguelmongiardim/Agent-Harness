from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def _write_patch_task(root: Path, task_id: str) -> Path:
    target = root / "fixture.py"
    target.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")
    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": task_id,
                "title": "Refactor",
                "intent": "Refactor add_numbers",
                "target_paths": ["fixture.py"],
                "allowed_tools": ["read_file", "patch_file"],
                "max_steps": 4,
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


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/runs/run-token-check/context",
        "/api/v1/runs/run-token-check/approvals",
        "/api/v1/policy/default",
    ],
)
def test_operator_inspection_routes_require_valid_token(tmp_path: Path, path: str) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    missing = TestClient(app).get(path)
    invalid = TestClient(app).get(
        path,
        headers={"X-Agent-Harness-Operator-Token": "wrong-secret"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "operator-secret" not in missing.text
    assert "operator-secret" not in invalid.text


def test_operator_approval_decision_route_requires_valid_token(tmp_path: Path) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    missing = TestClient(app).post(
        "/api/v1/runs/run-token-check/approvals/action-token-check/decision",
        json={"decision": "approve"},
    )
    invalid = TestClient(app).post(
        "/api/v1/runs/run-token-check/approvals/action-token-check/decision",
        headers={"X-Agent-Harness-Operator-Token": "wrong-secret"},
        json={"decision": "approve"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "operator-secret" not in missing.text
    assert "operator-secret" not in invalid.text


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


def test_operator_run_detail_denies_arbitrary_workspace_metadata_reference(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-denied-artifact")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-denied-artifact")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    secret_payload = {"api_key": "do-not-expose-this-secret"}
    (tmp_path / "secrets.json").write_text(json.dumps(secret_payload), encoding="utf-8")
    summary_path = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"] / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["artifacts"]["workspace_metadata"] = "secrets.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
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
    assert "workspace_metadata" not in body
    assert body["artifact_statuses"]["workspace_metadata"]["status"] == "denied"
    assert "secrets.json" not in response.text
    assert "do-not-expose-this-secret" not in response.text
    assert str(tmp_path) not in response.text


def test_operator_run_detail_does_not_echo_absolute_artifact_paths(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-absolute-path")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-absolute-path")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    absolute_path = str(tmp_path / "secret-context.json")
    run_dir = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"]
    for artifact_name in ("summary.json", "artifact-index.json"):
        artifact = json.loads((run_dir / artifact_name).read_text(encoding="utf-8"))
        artifact["artifacts"]["context_manifest"] = absolute_path
        (run_dir / artifact_name).write_text(json.dumps(artifact), encoding="utf-8")
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
    assert body["artifact_statuses"]["context_manifest"]["status"] == "denied"
    assert absolute_path not in response.text
    assert str(tmp_path) not in response.text


def test_operator_context_route_returns_existing_context_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-context")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    assert main(["inspect", "context", run_summary["run_id"]]) == 0
    cli_context = json.loads(capsys.readouterr().out)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}/context",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_context.v1"
    assert body["run_id"] == run_summary["run_id"]
    assert body["artifact"]["artifact_type"] == "context_manifest"
    assert body["artifact"]["status"] == "available"
    assert body["context_manifest"] == cli_context


def test_operator_context_route_reports_missing_context_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-missing-context")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-missing-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    context_path = (
        tmp_path / ".agent-harness" / "runs" / run_summary["run_id"] / "context_manifest.json"
    )
    context_path.unlink()
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}/context",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["artifact"]["artifact_type"] == "context_manifest"
    assert body["artifact"]["status"] == "missing"
    assert "context_manifest" not in body
    assert str(tmp_path) not in response.text


def test_operator_context_route_reports_malformed_context_manifest_safely(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "operator-malformed-context")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-malformed-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    context_path = (
        tmp_path / ".agent-harness" / "runs" / run_summary["run_id"] / "context_manifest.json"
    )
    context_path.write_text("{not-json", encoding="utf-8")
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}/context",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["artifact"]["artifact_type"] == "context_manifest"
    assert body["artifact"]["status"] == "malformed"
    assert "context_manifest" not in body
    assert str(tmp_path) not in response.text


def test_operator_policy_route_returns_redaction_safe_policy_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed_project(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_LIVE_TEST_API_KEY", "do-not-expose-env-secret")
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/policy/default",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_policy.v1"
    assert body["profile"] == "default"
    assert body["policy"]["schema_version"] == "policy.v2"
    assert body["policy"]["name"] == "default"
    assert "do-not-expose-env-secret" not in response.text
    assert str(tmp_path) not in response.text


def test_operator_approvals_route_lists_pending_approvals(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-approval-list")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-approval-list")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}/approvals",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_approval_list.v1"
    assert body["run_id"] == run_summary["run_id"]
    assert body["counts"] == {"pending": 1, "approved": 0, "denied": 0}
    assert [approval["action_id"] for approval in body["approvals"]] == [action_id]
    assert body["approvals"][0]["status"] == "pending"
    assert str(tmp_path) not in response.text


def test_operator_approval_decision_approves_through_existing_service(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-approval-decision")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-approval-decision")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:01:00Z")
    response = TestClient(app).post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={
            "decision": "approve",
            "actor": "operator",
            "reason": "reviewed in local UI",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "operator_approval_decision.v1"
    assert body["run_id"] == run_summary["run_id"]
    assert body["approval"]["action_id"] == action_id
    assert body["approval"]["status"] == "approved"
    assert body["approval"]["actor"] == "operator"
    assert body["approval"]["reason"] == "reviewed in local UI"

    run_dir = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"]
    approval_artifact = json.loads(
        (run_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8")
    )
    assert body["approval"] == approval_artifact
    assert (tmp_path / "fixture.py").read_text(encoding="utf-8") == (
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )

    assert main(["inspect", "run", run_summary["run_id"]]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["summary"]["status"] == "completed"
    assert any(event["type"] == "approval_decided" for event in inspected["events"])
    assert str(tmp_path) not in response.text


def test_operator_approval_decision_rejects_tampered_action_without_deciding(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-tampered-approval")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-tampered-approval")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    run_dir = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"]
    action_path = run_dir / "actions" / f"{action_id}.json"
    action = json.loads(action_path.read_text(encoding="utf-8"))
    action["call"]["arguments"]["proposed_content"] = "tampered\n"
    action_path.write_text(json.dumps(action), encoding="utf-8")
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "approve", "actor": "operator"},
    )

    assert response.status_code == 422
    assert "approval binding" in response.json()["detail"]
    approval_artifact = json.loads(
        (run_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8")
    )
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert approval_artifact["status"] == "pending"
    assert not any(event["type"] == "approval_decided" for event in events)
    assert (tmp_path / "fixture.py").read_text(encoding="utf-8") == (
        "def add_numbers(a, b):\n    return a + b\n"
    )
    assert str(tmp_path) not in response.text


def test_operator_approval_decision_rejects_checkpoint_drift_without_deciding(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-checkpoint-drift")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-checkpoint-drift")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    run_dir = tmp_path / ".agent-harness" / "runs" / run_summary["run_id"]
    approval_path = run_dir / "approvals" / f"{action_id}.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["checkpoint_hash"] = "drifted-checkpoint"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "approve", "actor": "operator"},
    )

    assert response.status_code == 422
    assert "approval binding" in response.json()["detail"]
    approval_artifact = json.loads(approval_path.read_text(encoding="utf-8"))
    assert approval_artifact["status"] == "pending"
    assert approval_artifact["checkpoint_hash"] == "drifted-checkpoint"
    assert (tmp_path / "fixture.py").read_text(encoding="utf-8") == (
        "def add_numbers(a, b):\n    return a + b\n"
    )
    assert str(tmp_path) not in response.text


def test_operator_approval_decision_denies_and_lists_decided_approval(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-deny-approval")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-deny-approval")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "deny"},
    )
    listed = TestClient(app).get(
        f"/api/v1/runs/{run_summary['run_id']}/approvals",
        headers=_operator_headers(),
    )

    assert response.status_code == 200
    assert response.json()["approval"]["status"] == "denied"
    assert response.json()["approval"]["actor"] == "operator"
    assert listed.status_code == 200
    assert listed.json()["counts"] == {"pending": 0, "approved": 0, "denied": 1}
    assert listed.json()["approvals"][0]["status"] == "denied"
    assert (tmp_path / "fixture.py").read_text(encoding="utf-8") == (
        "def add_numbers(a, b):\n    return a + b\n"
    )

    assert main(["inspect", "run", run_summary["run_id"]]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["summary"]["status"] == "failed"
    assert any(event["type"] == "approval_decided" for event in inspected["events"])


def test_operator_approval_decision_reports_boundary_errors_safely(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    task_path = _write_patch_task(tmp_path, "operator-approval-errors")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-operator-approval-errors")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    action_id = run_summary["approvals"][0]
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )
    client = TestClient(app)

    invalid_decision = client.post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "maybe"},
    )
    missing_action = client.post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/action-does-not-exist/decision",
        headers=_operator_headers(),
        json={"decision": "approve"},
    )
    missing_run = client.post(
        "/api/v1/runs/run-does-not-exist/approvals/action-does-not-exist/decision",
        headers=_operator_headers(),
        json={"decision": "approve"},
    )
    first_decision = client.post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "deny"},
    )
    conflict = client.post(
        f"/api/v1/runs/{run_summary['run_id']}/approvals/{action_id}/decision",
        headers=_operator_headers(),
        json={"decision": "approve"},
    )

    assert invalid_decision.status_code == 422
    assert missing_action.status_code == 404
    assert missing_action.json()["detail"] == "approval action not found"
    assert missing_run.status_code == 404
    assert missing_run.json()["detail"] == "run not found"
    assert first_decision.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "approval is already denied"
    for response in (invalid_decision, missing_action, missing_run, conflict):
        assert "operator-secret" not in response.text
        assert str(tmp_path) not in response.text
