from __future__ import annotations

import json
import re
import secrets
from html import escape
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ValidationError

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.core.runtime import approve_action
from agent_harness.evidence.schema import (
    ControlMapping,
    EvidenceFindingsExport,
    EvidenceIndex,
    EvidenceManifest,
    EvidencePack,
)
from agent_harness.operator.schema import (
    OperatorApprovalDecisionRequest,
    OperatorApprovalDecisionResponse,
    OperatorApprovalListResponse,
    OperatorArtifactStatus,
    OperatorContextResponse,
    OperatorEvidenceArtifactIndexResponse,
    OperatorEvidenceControlMappingResponse,
    OperatorEvidenceFindingsResponse,
    OperatorEvidenceOverviewResponse,
    OperatorEvidencePackDetailResponse,
    OperatorEvidencePackListResponse,
    OperatorEvidencePackSummary,
    OperatorHealthResponse,
    OperatorPolicyResponse,
    OperatorRunDetailResponse,
    OperatorRunListResponse,
)
from agent_harness.policy import PolicyError, load_policy
from agent_harness.storage import RunStore
from agent_harness.storage.schema import ApprovalRecord
from agent_harness.utils import load_json, normalize_relative_path

OPERATOR_TOKEN_HEADER = "X-Agent-Harness-Operator-Token"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
STATIC_ASSET_TYPES = {
    "app.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}
TModel = TypeVar("TModel", bound=BaseModel)


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

    @app.get("/", response_class=HTMLResponse)
    def operator_ui() -> HTMLResponse:
        return HTMLResponse(
            _read_index_html(app.state.profile),
            media_type="text/html; charset=utf-8",
        )

    @app.get("/operator/static/{asset_name}")
    def operator_static(asset_name: str) -> Response:
        media_type = STATIC_ASSET_TYPES.get(asset_name)
        if media_type is None:
            raise HTTPException(status_code=404, detail="static asset not found")
        return Response(
            _read_static_text(asset_name),
            media_type=media_type,
        )

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

    @app.get("/api/v1/runs/{run_id}/approvals")
    def run_approvals(
        run_id: str,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_approvals(app.state.project_root, run_id).model_dump(mode="json")

    @app.post("/api/v1/runs/{run_id}/approvals/{action_id}/decision")
    def approval_decision(
        run_id: str,
        action_id: str,
        request: OperatorApprovalDecisionRequest,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _decide_approval(app.state.project_root, run_id, action_id, request).model_dump(
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

    @app.get("/api/v1/evidence/overview")
    def evidence_overview(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_evidence_overview(app.state.project_root).model_dump(
            mode="json",
            exclude_none=True,
        )

    @app.get("/api/v1/evidence/packs")
    def evidence_packs(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        return _load_evidence_pack_list(app.state.project_root).model_dump(mode="json")

    @app.get("/api/v1/evidence/packs/{pack_id}")
    def evidence_pack_detail(
        pack_id: str,
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        pack_dir = _find_evidence_pack_dir(app.state.project_root, pack_id)
        return _load_evidence_pack_detail(app.state.project_root, pack_dir).model_dump(mode="json")

    @app.get("/api/v1/evidence/control-map")
    def evidence_control_map(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        detail = _load_current_evidence_pack_detail(app.state.project_root)
        return OperatorEvidenceControlMappingResponse(
            pack_id=detail.pack_id,
            path=detail.path,
            control_mapping=detail.control_mapping,
        ).model_dump(mode="json")

    @app.get("/api/v1/evidence/artifact-index")
    def evidence_artifact_index(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        detail = _load_current_evidence_pack_detail(app.state.project_root)
        return OperatorEvidenceArtifactIndexResponse(
            pack_id=detail.pack_id,
            path=detail.path,
            artifact_index=detail.artifact_index,
        ).model_dump(mode="json")

    @app.get("/api/v1/evidence/findings")
    def evidence_findings(
        _authorized: None = Depends(require_operator_token),
    ) -> dict[str, object]:
        del _authorized
        detail = _load_current_evidence_pack_detail(app.state.project_root)
        return OperatorEvidenceFindingsResponse(
            pack_id=detail.pack_id,
            path=detail.path,
            findings=detail.findings,
        ).model_dump(mode="json")

    @app.api_route(
        "/api/v1/evidence/{path:path}",
        methods=["DELETE", "PATCH", "POST", "PUT"],
    )
    def evidence_read_only(
        path: str,
        _authorized: None = Depends(require_operator_token),
    ) -> None:
        del path, _authorized
        raise HTTPException(status_code=405, detail="evidence API is read-only")

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


def _read_static_text(name: str) -> str:
    return (
        resources.files("agent_harness.operator.static").joinpath(name).read_text(encoding="utf-8")
    )


def _read_index_html(profile: str) -> str:
    return _read_static_text("index.html").replace(
        "__OPERATOR_PROFILE__",
        escape(profile, quote=True),
    )


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
        skill_manifest=_read_optional_run_data(store, "skill_manifest.json"),
        template_apply=_read_optional_run_data(store, "template_apply.json"),
        git_commit=_read_optional_run_data(store, "git_commit.json"),
        eval_results=_read_optional_run_data(store, "eval_results.json"),
        retrieval_scorecards=_read_optional_run_data(store, "retrieval_scorecards.json"),
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


def _load_approvals(project_root: Path, run_id: str) -> OperatorApprovalListResponse:
    store = _open_run_store(project_root, run_id)
    approval_dir = store.run_dir / "approvals"
    approvals: list[dict[str, Any]] = []
    counts = {"pending": 0, "approved": 0, "denied": 0}
    if approval_dir.exists():
        for path in sorted(approval_dir.glob("*.json")):
            try:
                approval = ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail="malformed run artifact: approvals",
                ) from exc
            approvals.append(approval.model_dump(mode="json"))
            counts[approval.status] += 1
    return OperatorApprovalListResponse(
        run_id=run_id,
        approvals=approvals,
        counts=counts,
    )


def _decide_approval(
    project_root: Path,
    run_id: str,
    action_id: str,
    request: OperatorApprovalDecisionRequest,
) -> OperatorApprovalDecisionResponse:
    store = _open_run_store(project_root, run_id)
    if RUN_ID_PATTERN.fullmatch(action_id) is None:
        raise HTTPException(status_code=404, detail="approval action not found")
    if not (store.run_dir / "approvals" / f"{action_id}.json").exists():
        raise HTTPException(status_code=404, detail="approval action not found")
    try:
        approval = approve_action(
            project_root,
            run_id,
            action_id,
            request.decision,
            actor=request.actor or "operator",
            reason=request.reason,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="approval action not found") from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if detail.startswith("approval is already ") else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return OperatorApprovalDecisionResponse(
        run_id=run_id,
        approval=approval.model_dump(mode="json"),
    )


def _load_evidence_overview(project_root: Path) -> OperatorEvidenceOverviewResponse:
    pack_list = _load_evidence_pack_list(project_root)
    current_pack = pack_list.packs[-1] if pack_list.packs else None
    return OperatorEvidenceOverviewResponse(
        status="available" if current_pack is not None else "missing",
        evidence_root=pack_list.evidence_root,
        pack_count=pack_list.count,
        current_pack=current_pack,
    )


def _load_evidence_pack_list(project_root: Path) -> OperatorEvidencePackListResponse:
    evidence_root = _evidence_root(project_root)
    summaries = [
        _evidence_pack_summary(project_root, pack_dir)
        for pack_dir in _evidence_pack_directories(project_root)
    ]
    summaries.sort(key=lambda summary: (summary.generated_at, summary.pack_id))
    return OperatorEvidencePackListResponse(
        evidence_root=_safe_project_relative(project_root, evidence_root),
        packs=summaries,
        count=len(summaries),
    )


def _load_current_evidence_pack_detail(project_root: Path) -> OperatorEvidencePackDetailResponse:
    pack_dir = _current_evidence_pack_dir(project_root)
    if pack_dir is None:
        raise HTTPException(status_code=404, detail="evidence pack not found")
    return _load_evidence_pack_detail(project_root, pack_dir)


def _load_evidence_pack_detail(
    project_root: Path,
    pack_dir: Path,
) -> OperatorEvidencePackDetailResponse:
    pack = _read_evidence_model(project_root, pack_dir, "evidence_pack.v1.json", EvidencePack)
    manifest = _read_evidence_model(
        project_root,
        pack_dir,
        "evidence_manifest.v1.json",
        EvidenceManifest,
    )
    index = _read_evidence_model(
        project_root,
        pack_dir,
        "evidence_index.v1.json",
        EvidenceIndex,
    )
    findings = _read_evidence_model(
        project_root,
        pack_dir,
        "evidence_findings.v1.json",
        EvidenceFindingsExport,
    )
    control_mapping = _read_evidence_model(
        project_root,
        pack_dir,
        "control_mapping.v1.json",
        ControlMapping,
    )
    return OperatorEvidencePackDetailResponse(
        pack_id=pack.pack_id,
        path=_safe_project_relative(project_root, pack_dir / "evidence_pack.v1.json"),
        evidence_pack=pack.model_dump(mode="json"),
        manifest=manifest.model_dump(mode="json"),
        artifact_index=index.model_dump(mode="json"),
        findings=findings.model_dump(mode="json"),
        control_mapping=control_mapping.model_dump(mode="json"),
    )


def _evidence_pack_summary(project_root: Path, pack_dir: Path) -> OperatorEvidencePackSummary:
    pack = _read_evidence_model(project_root, pack_dir, "evidence_pack.v1.json", EvidencePack)
    findings = _read_optional_evidence_model(
        project_root,
        pack_dir,
        "evidence_findings.v1.json",
        EvidenceFindingsExport,
    )
    finding_count = findings.counts.total if findings is not None else 0
    blocking_findings = (
        sum(
            1
            for finding in findings.findings
            if finding.blocks_evidence_pack or finding.blocks_release
        )
        if findings is not None
        else 0
    )
    return OperatorEvidencePackSummary(
        pack_id=pack.pack_id,
        path=_safe_project_relative(project_root, pack_dir / "evidence_pack.v1.json"),
        generated_at=pack.generated_at,
        profile=pack.profile,
        claim_status=pack.claim_status,
        redaction_status=pack.redaction_status,
        findings_count=finding_count,
        blocking_findings=blocking_findings,
    )


def _find_evidence_pack_dir(project_root: Path, pack_id: str) -> Path:
    if RUN_ID_PATTERN.fullmatch(pack_id) is None:
        raise HTTPException(status_code=404, detail="evidence pack not found")
    for pack_dir in _evidence_pack_directories(project_root):
        pack = _read_evidence_model(project_root, pack_dir, "evidence_pack.v1.json", EvidencePack)
        if pack.pack_id == pack_id:
            return pack_dir
    raise HTTPException(status_code=404, detail="evidence pack not found")


def _current_evidence_pack_dir(project_root: Path) -> Path | None:
    records: list[tuple[EvidencePack, Path]] = []
    for pack_dir in _evidence_pack_directories(project_root):
        pack = _read_evidence_model(project_root, pack_dir, "evidence_pack.v1.json", EvidencePack)
        records.append((pack, pack_dir))
    if not records:
        return None
    records.sort(key=lambda record: (record[0].generated_at, record[0].pack_id))
    return records[-1][1]


def _evidence_pack_directories(project_root: Path) -> list[Path]:
    evidence_root = _evidence_root(project_root)
    if not evidence_root.exists() or not evidence_root.is_dir():
        return []
    directories: list[Path] = []
    if (evidence_root / "evidence_pack.v1.json").exists():
        directories.append(evidence_root)
    for child in sorted(evidence_root.iterdir()):
        if child.name == "archive" or child.is_symlink() or not child.is_dir():
            continue
        try:
            child.resolve().relative_to(evidence_root.resolve())
        except ValueError:
            continue
        if (child / "evidence_pack.v1.json").exists():
            directories.append(child)
    return directories


def _read_evidence_model(
    project_root: Path,
    pack_dir: Path,
    filename: str,
    model: type[TModel],
) -> TModel:
    path = _safe_evidence_artifact_path(project_root, pack_dir, filename)
    if not path.exists():
        raise HTTPException(
            status_code=422,
            detail=f"missing required evidence artifact: {filename}",
        )
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"malformed evidence artifact: {filename}",
        ) from exc


def _read_optional_evidence_model(
    project_root: Path,
    pack_dir: Path,
    filename: str,
    model: type[TModel],
) -> TModel | None:
    path = _safe_evidence_artifact_path(project_root, pack_dir, filename)
    if not path.exists():
        return None
    return _read_evidence_model(project_root, pack_dir, filename, model)


def _safe_evidence_artifact_path(project_root: Path, pack_dir: Path, filename: str) -> Path:
    evidence_root = _evidence_root(project_root).resolve()
    path = pack_dir / filename
    try:
        path.resolve().relative_to(evidence_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="denied evidence artifact reference",
        ) from exc
    return path


def _evidence_root(project_root: Path) -> Path:
    return _artifact_root(project_root) / "evidence"


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
