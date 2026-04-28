from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_harness import __version__
from agent_harness.operator import create_operator_app


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


def test_operator_api_accepts_valid_token_before_route_implementation(
    tmp_path: Path,
) -> None:
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    response = TestClient(app).get(
        "/api/v1/runs",
        headers={"X-Agent-Harness-Operator-Token": "operator-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "operator API route not implemented"
    assert "operator-secret" not in response.text
