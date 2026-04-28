from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.schemas import (
    OperatorHealthResponse,
    OperatorRunDetailResponse,
    OperatorRunListResponse,
)
from agent_harness.storage import RunStore
from agent_harness.utils import load_json, normalize_relative_path

OPERATOR_TOKEN_HEADER = "X-Agent-Harness-Operator-Token"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def create_operator_app(project_root: Path, token: str, profile: str = "default") -> FastAPI:
    app = FastAPI(title="Agent Harness Operator", version=__version__)
    app.state.project_root = project_root.resolve()
    app.state.operator_token = token
    app.state.profile = profile

    def require_operator_token(
        provided_token: str | None = Header(default=None, alias=OPERATOR_TOKEN_HEADER),
    ) -> None:
        if provided_token is None or not secrets.compare_digest(provided_token, token):
            raise HTTPException(
                status_code=401,
                detail="missing or invalid operator token",
            )

    @app.get("/health")
    def health() -> dict[str, object]:
        return OperatorHealthResponse(
            agent_harness_version=__version__,
        ).model_dump(mode="json")

    @app.get("/api/v1/runs")
    def run_list(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_run_list(app.state.project_root).model_dump(mode="json")

    @app.get("/api/v1/runs/{run_id}")
    def run_detail(
        run_id: str,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_run_detail(app.state.project_root, run_id).model_dump(
            mode="json",
            exclude_none=True,
        )

    @app.api_route(
        "/api/v1/{path:path}",
        methods=["DELETE", "GET", "PATCH", "POST", "PUT"],
    )
    def api_not_implemented(
        path: str,
        _authorized: None = Depends(require_operator_token),
    ) -> None:
        del path, _authorized
        raise HTTPException(status_code=404, detail="operator API route not implemented")

    return app


def _load_run_list(project_root: Path) -> OperatorRunListResponse:
    artifact_root = _artifact_root(project_root)
    runs_root = artifact_root / "runs"
    if not runs_root.exists():
        return OperatorRunListResponse(runs=[], count=0)
    summaries = [
        _read_required_run_data(RunStore.open_existing(artifact_root, path.name), "summary.json")
        for path in sorted(runs_root.iterdir())
        if path.is_dir() and RUN_ID_PATTERN.fullmatch(path.name) is not None
    ]
    return OperatorRunListResponse(runs=summaries, count=len(summaries))


def _load_run_detail(project_root: Path, run_id: str) -> OperatorRunDetailResponse:
    store = _open_run_store(project_root, run_id)
    summary = _read_required_run_data(store, "summary.json")
    detail = OperatorRunDetailResponse(
        run_id=run_id,
        summary=summary,
        events=_read_run_events(store),
        artifact_index=_read_required_run_data(store, "artifact-index.json"),
        provider=_read_optional_run_data(store, "provider.json"),
        provider_calls=_read_optional_run_data(store, "provider_calls.json"),
        provider_input=_read_optional_run_data(store, "provider_input.json"),
        security_findings=_read_optional_run_data(store, "security_findings.json"),
        runtime_adapter=_read_optional_run_data(store, "runtime_adapter.json"),
        schema_versions=_read_optional_run_data(store, "schema_versions.json"),
        template_apply=_read_optional_run_data(store, "template_apply.json"),
        git_commit=_read_optional_run_data(store, "git_commit.json"),
        workspace_metadata=_read_workspace_metadata(project_root, summary),
    )
    return detail


def _open_run_store(project_root: Path, run_id: str) -> RunStore:
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    artifact_root = _artifact_root(project_root)
    try:
        return RunStore.open_existing(artifact_root, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc


def _artifact_root(project_root: Path) -> Path:
    return project_root / load_config(project_root).artifact_root


def _read_required_run_data(store: RunStore, relative: str) -> dict[str, Any]:
    try:
        return store.read_data(relative)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"missing required run artifact: {relative}",
        ) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"malformed run artifact: {relative}",
        ) from exc


def _read_optional_run_data(store: RunStore, relative: str) -> dict[str, Any] | None:
    if not (store.run_dir / relative).exists():
        return None
    return _read_required_run_data(store, relative)


def _read_run_events(store: RunStore) -> list[dict[str, Any]]:
    try:
        return store.events()
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="malformed run artifact: events.jsonl",
        ) from exc


def _read_workspace_metadata(project_root: Path, summary: dict[str, Any]) -> dict[str, Any] | None:
    artifacts = summary.get("artifacts")
    workspace_reference = (
        artifacts.get("workspace_metadata") if isinstance(artifacts, dict) else None
    )
    if not isinstance(workspace_reference, str):
        return None
    try:
        safe_reference = normalize_relative_path(workspace_reference)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="malformed run artifact reference: workspace_metadata",
        ) from exc
    workspace_path = project_root / safe_reference
    try:
        workspace_path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="denied run artifact reference: workspace_metadata",
        ) from exc
    if not workspace_path.exists():
        return None
    try:
        loaded = load_json(workspace_path)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail="malformed run artifact: workspace_metadata",
        ) from exc
    if not isinstance(loaded, dict):
        raise HTTPException(
            status_code=422,
            detail="malformed run artifact: workspace_metadata",
        )
    return loaded
