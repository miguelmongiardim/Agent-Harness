from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_harness.config import load_config
from agent_harness.policy import PolicyError, load_policy
from agent_harness.storage import RunStore
from agent_harness.utils import now_utc

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def list_mcp_resources(project_root: Path, profile: str = "default") -> dict[str, Any]:
    root = project_root.resolve()
    artifact_root = root / load_config(root).artifact_root
    resources = [
        {
            "uri": "agent-harness://runs",
            "resource_type": "run_collection",
            "mime_type": "application/json",
            "name": "runs",
            "description": "Available Agent Harness runs.",
        }
    ]
    runs_root = artifact_root / "runs"
    if runs_root.exists():
        for run_dir in sorted(runs_root.iterdir()):
            if not run_dir.is_dir() or RUN_ID_PATTERN.fullmatch(run_dir.name) is None:
                continue
            if (run_dir / "summary.json").exists():
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "summary",
                        "run_summary",
                        run_dir / "summary.json",
                    )
                )
            if (run_dir / "context_manifest.json").exists():
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "context",
                        "run_context",
                        run_dir / "context_manifest.json",
                    )
                )
    return {
        "schema_version": "mcp_resource_list.v1",
        "profile": profile,
        "resources": resources,
        "count": len(resources),
    }


def read_mcp_resource(project_root: Path, uri: str, profile: str = "default") -> dict[str, Any]:
    root = project_root.resolve()
    artifact_root = root / load_config(root).artifact_root
    try:
        load_policy(root, profile)
    except PolicyError:
        envelope = _denial_envelope(uri, profile, "unknown_profile")
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="denied",
            denial_reason="unknown_profile",
        )
        return envelope
    try:
        run_id, resource_name = _parse_run_resource_uri(uri)
    except ValueError as exc:
        reason = str(exc)
        envelope = _denial_envelope(uri, profile, reason)
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="denied",
            denial_reason=reason,
        )
        return envelope
    store = RunStore.open_existing(artifact_root, run_id)
    if resource_name == "summary":
        relative = "summary.json"
        resource_type = "run_summary"
    elif resource_name == "context":
        relative = "context_manifest.json"
        resource_type = "run_context"
    else:
        raise ValueError(f"unsupported MCP run resource: {resource_name}")
    content = store.read_data(relative)
    envelope = {
        "schema_version": "mcp_resource_envelope.v1",
        "uri": uri,
        "mime_type": "application/json",
        "resource_type": resource_type,
        "source_artifact": _safe_project_relative(root, store.run_dir / relative),
        "source_schema_version": content.get("schema_version"),
        "policy_profile": profile,
        "policy_decision_id": None,
        "redaction_applied": False,
        "denial_status": "allowed",
        "content": content,
        "metadata": {"run_id": run_id},
    }
    _append_access_log(
        artifact_root,
        uri=uri,
        profile=profile,
        result="allowed",
        run_id=run_id,
        artifact_type=resource_type,
    )
    return envelope


def _resource_descriptor(
    project_root: Path,
    run_id: str,
    name: str,
    resource_type: str,
    artifact_path: Path,
) -> dict[str, str]:
    return {
        "uri": f"agent-harness://runs/{run_id}/{name}",
        "resource_type": resource_type,
        "mime_type": "application/json",
        "name": f"{run_id}/{name}",
        "source_artifact": _safe_project_relative(project_root, artifact_path),
    }


def _parse_run_resource_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "agent-harness":
        raise ValueError("unsupported_uri_scheme")
    if parsed.netloc != "runs":
        raise ValueError("unknown_resource")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("query_or_fragment_not_allowed")
    parts = parsed.path.lstrip("/").split("/")
    if len(parts) != 2:
        raise ValueError("unknown_resource")
    run_id, resource_name = parts
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("unsafe_run_id")
    if resource_name not in {"summary", "context"}:
        raise ValueError("unknown_resource")
    return run_id, resource_name


def _denial_envelope(uri: str, profile: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "mcp_resource_envelope.v1",
        "uri": uri,
        "mime_type": "application/json",
        "resource_type": "denial",
        "source_artifact": None,
        "source_schema_version": None,
        "policy_profile": profile,
        "policy_decision_id": None,
        "redaction_applied": False,
        "denial_status": "denied",
        "content": None,
        "metadata": {"denial_reason": reason},
    }


def _append_access_log(
    artifact_root: Path,
    *,
    uri: str,
    profile: str,
    result: str,
    run_id: str | None = None,
    artifact_type: str | None = None,
    denial_reason: str | None = None,
) -> None:
    record = {
        "schema_version": "mcp_access_log.v1",
        "timestamp": now_utc().isoformat(),
        "transport": "cli",
        "request_type": "resource_read",
        "resource_uri": uri,
        "run_id": run_id,
        "artifact_type": artifact_type,
        "policy_profile": profile,
        "policy_decision_id": None,
        "result": result,
        "redaction_applied": False,
        "denial_reason": denial_reason,
    }
    path = artifact_root / "mcp" / "access-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _safe_project_relative(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()
