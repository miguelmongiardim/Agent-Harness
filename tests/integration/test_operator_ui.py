from __future__ import annotations

import importlib.resources
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from agent_harness.operator import create_operator_app
from tests.conftest import seed_project

FORBIDDEN_REMOTE_MARKERS = (
    "http://",
    "https://",
    "//cdn",
    "googleapis",
    "gstatic",
    "analytics",
    "localStorage",
    "sessionStorage",
)


def test_operator_root_serves_packaged_local_only_ui_shell(tmp_path: Path) -> None:
    seed_project(tmp_path)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Agent Harness Operator" in response.text
    assert "Local-only / non-hosted" in response.text
    assert 'href="/operator/static/app.css"' in response.text
    assert 'src="/operator/static/app.js"' in response.text
    assert _remote_markers(response.text) == []

    css = client.get("/operator/static/app.css")
    script = client.get("/operator/static/app.js")

    assert css.status_code == 200
    assert script.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert script.headers["content-type"].startswith("text/javascript")
    assert _remote_markers(css.text) == []
    assert _remote_markers(script.text) == []


def test_operator_ui_script_uses_only_local_api_routes(tmp_path: Path) -> None:
    seed_project(tmp_path)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    script = TestClient(app).get("/operator/static/app.js").text

    assert "/api/v1/runs" in script
    assert "/context" in script
    assert "/approvals" in script
    assert "/api/v1/policy/" in script
    assert "fetch(path, " in script
    assert _remote_markers(script) == []


def test_operator_ui_approval_panel_posts_decisions_to_existing_local_api(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    app = create_operator_app(
        project_root=tmp_path,
        token="operator-secret",
        profile="default",
    )

    script = TestClient(app).get("/operator/static/app.js").text

    assert "/approvals/${encodeURIComponent(actionId)}/decision" in script
    assert 'method: "POST"' in script
    assert '"Content-Type": "application/json"' in script
    assert 'decision: "approve"' in script
    assert 'decision: "deny"' in script
    assert "Pending" in script
    assert "Approved" in script
    assert "Denied" in script
    assert "Already decided as" in script
    assert "approval-actor" in script
    assert "approval-reason" in script
    assert "refreshSelectedRun" in script
    assert "setStatus(elements.detailStatus, error.message, true)" in script
    assert _remote_markers(script) == []


def test_operator_static_ui_files_are_packaged() -> None:
    package_files = importlib.resources.files("agent_harness.operator.static")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["agent_harness"]

    for name in ["index.html", "app.css", "app.js"]:
        assert package_files.joinpath(name).is_file()
    assert "operator/static/*.html" in package_data
    assert "operator/static/*.css" in package_data
    assert "operator/static/*.js" in package_data


def _remote_markers(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in FORBIDDEN_REMOTE_MARKERS if marker.lower() in lowered]
