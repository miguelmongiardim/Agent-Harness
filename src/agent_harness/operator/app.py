from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.policy import PolicyError, load_policy
from agent_harness.schemas import (
    OperatorArtifactStatus,
    OperatorContextResponse,
    OperatorHealthResponse,
    OperatorPolicyResponse,
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

    @app.get("/api/v1/runs/{run_id}/context")
    def run_context(
        run_id: str,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_context_manifest(app.state.project_root, run_id).model_dump(
            mode="json",
            exclude_none=True,
        )

    @app.get("/api/v1/policy/{profile}")
    def policy_summary(
        profile: str,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_policy_summary(app.state.project_root, profile).model_dump(mode="json")

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
    artifact_index = _read_required_run_data(store, "artifact-index.json")
    workspace_metadata, workspace_status = _read_workspace_metadata(project_root, summary)
    artifact_statuses: dict[str, OperatorArtifactStatus] = {}
    if workspace_status is not None:
        artifact_statuses["workspace_metadata"] = workspace_status
        if workspace_status.status != "available":
            summary = _without_artifact_reference(summary, "workspace_metadata")
    summary = _sanitize_artifact_references(summary, artifact_statuses)
    artifact_index = _sanitize_artifact_references(artifact_index, artifact_statuses)
    detail = OperatorRunDetailResponse(
        run_id=run_id,
        summary=summary,
        events=_read_run_events(store),
        artifact_index=artifact_index,
        provider=_read_optional_run_data(store, "provider.json"),
        provider_calls=_read_optional_run_data(store, "provider_calls.json"),
        provider_input=_read_optional_run_data(store, "provider_input.json"),
        security_findings=_read_optional_run_data(store, "security_findings.json"),
        runtime_adapter=_read_optional_run_data(store, "runtime_adapter.json"),
        schema_versions=_read_optional_run_data(store, "schema_versions.json"),
        template_apply=_read_optional_run_data(store, "template_apply.json"),
        git_commit=_read_optional_run_data(store, "git_commit.json"),
        workspace_metadata=workspace_metadata,
        artifact_statuses=artifact_statuses,
    )
    return detail


def _load_context_manifest(project_root: Path, run_id: str) -> OperatorContextResponse:
    store = _open_run_store(project_root, run_id)
    context_path = store.run_dir / "context_manifest.json"
    safe_path = _safe_project_relative(project_root, context_path)
    if not context_path.exists():
        return OperatorContextResponse(
            run_id=run_id,
            artifact=OperatorArtifactStatus(
                artifact_type="context_manifest",
                status="missing",
                path=safe_path,
            ),
        )
    try:
        context_manifest = store.read_data("context_manifest.json")
    except (json.JSONDecodeError, ValueError):
        return OperatorContextResponse(
            run_id=run_id,
            artifact=OperatorArtifactStatus(
                artifact_type="context_manifest",
                status="malformed",
                path=safe_path,
                detail="context manifest artifact is malformed",
            ),
        )
    return OperatorContextResponse(
        run_id=run_id,
        artifact=OperatorArtifactStatus(
            artifact_type="context_manifest",
            status="available",
            path=safe_path,
        ),
        context_manifest=context_manifest,
    )


def _load_policy_summary(project_root: Path, profile: str) -> OperatorPolicyResponse:
    if RUN_ID_PATTERN.fullmatch(profile) is None:
        raise HTTPException(status_code=404, detail="policy profile not found")
    try:
        policy = load_policy(project_root, profile)
    except PolicyError as exc:
        raise HTTPException(status_code=404, detail="policy profile not found") from exc
    return OperatorPolicyResponse(
        profile=profile,
        policy=policy.model_dump(mode="json"),
    )


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


def _without_artifact_reference(summary: dict[str, Any], artifact_name: str) -> dict[str, Any]:
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict) or artifact_name not in artifacts:
        return summary
    sanitized = dict(summary)
    sanitized_artifacts = dict(artifacts)
    sanitized_artifacts.pop(artifact_name, None)
    sanitized["artifacts"] = sanitized_artifacts
    return sanitized


def _sanitize_artifact_references(
    payload: dict[str, Any],
    artifact_statuses: dict[str, OperatorArtifactStatus],
) -> dict[str, Any]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return payload
    sanitized_artifacts = dict(artifacts)
    changed = False
    for artifact_name, reference in artifacts.items():
        if isinstance(artifact_name, str) and _is_safe_relative_artifact_reference(reference):
            continue
        sanitized_artifacts.pop(artifact_name, None)
        if isinstance(artifact_name, str):
            artifact_statuses.setdefault(
                artifact_name,
                OperatorArtifactStatus(
                    artifact_type=artifact_name,
                    status="denied",
                    detail="artifact reference is not a safe relative path",
                ),
            )
        changed = True
    if not changed:
        return payload
    sanitized = dict(payload)
    sanitized["artifacts"] = sanitized_artifacts
    return sanitized


def _is_safe_relative_artifact_reference(reference: object) -> bool:
    if not isinstance(reference, str):
        return False
    if re.match(r"^[A-Za-z]:[\\/]", reference):
        return False
    try:
        normalize_relative_path(reference)
    except ValueError:
        return False
    return True


def _read_workspace_metadata(
    project_root: Path, summary: dict[str, Any]
) -> tuple[dict[str, Any] | None, OperatorArtifactStatus | None]:
    artifacts = summary.get("artifacts")
    workspace_reference = (
        artifacts.get("workspace_metadata") if isinstance(artifacts, dict) else None
    )
    if not isinstance(workspace_reference, str):
        return None, None
    try:
        safe_reference = normalize_relative_path(workspace_reference)
    except ValueError:
        return None, OperatorArtifactStatus(
            artifact_type="workspace_metadata",
            status="malformed",
            detail="workspace metadata reference is not a normalized relative path",
        )
    workspace_path = (project_root / safe_reference).resolve()
    allowed_workspace_path = (_artifact_root(project_root) / "workspace.json").resolve()
    if workspace_path != allowed_workspace_path:
        return None, OperatorArtifactStatus(
            artifact_type="workspace_metadata",
            status="denied",
            detail="workspace metadata reference is not an allowlisted artifact path",
        )
    safe_path = _safe_project_relative(project_root, workspace_path)
    if not workspace_path.exists():
        return None, OperatorArtifactStatus(
            artifact_type="workspace_metadata",
            status="missing",
            path=safe_path,
        )
    try:
        loaded = load_json(workspace_path)
    except json.JSONDecodeError:
        return None, OperatorArtifactStatus(
            artifact_type="workspace_metadata",
            status="malformed",
            path=safe_path,
            detail="workspace metadata artifact is not valid JSON",
        )
    if not isinstance(loaded, dict):
        return None, OperatorArtifactStatus(
            artifact_type="workspace_metadata",
            status="malformed",
            path=safe_path,
            detail="workspace metadata artifact is not a JSON object",
        )
    return loaded, OperatorArtifactStatus(
        artifact_type="workspace_metadata",
        status="available",
        path=safe_path,
    )


def _safe_project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="denied run artifact reference",
        ) from exc
