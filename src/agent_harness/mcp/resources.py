from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_harness.config import load_config
from agent_harness.policy import PolicyError, load_policy, load_policy_with_schema_evidence
from agent_harness.skills import list_skills, load_skill_detail
from agent_harness.storage import RunStore
from agent_harness.templates import list_templates, load_template
from agent_harness.utils import now_utc

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


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
        },
        {
            "uri": "agent-harness://templates",
            "resource_type": "template_collection",
            "mime_type": "application/json",
            "name": "templates",
            "description": "Available Agent Harness templates.",
        },
        {
            "uri": "agent-harness://skills",
            "resource_type": "skill_collection",
            "mime_type": "application/json",
            "name": "skills",
            "description": "Available Agent Harness skills.",
        },
    ]
    try:
        load_policy(root, profile)
    except PolicyError:
        pass
    else:
        resources.append(
            {
                "uri": f"agent-harness://policies/{profile}",
                "resource_type": "policy_summary",
                "mime_type": "application/json",
                "name": profile,
                "source_artifact": f"policies/{profile}.json",
            }
        )
    for template in list_templates(root):
        resources.append(
            {
                "uri": f"agent-harness://templates/{template.template_id}",
                "resource_type": "template_detail",
                "mime_type": "application/json",
                "name": template.template_id,
                "source_artifact": template.bundle_path,
            }
        )
    for skill in list_skills(root):
        resources.append(
            {
                "uri": f"agent-harness://skills/{skill.skill_id}",
                "resource_type": "skill_detail",
                "mime_type": "application/json",
                "name": skill.skill_id,
                "source_artifact": skill.source,
            }
        )
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
        resource = _parse_resource_uri(uri)
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
    if resource["kind"] == "template_collection":
        records = [template.model_dump(mode="json") for template in list_templates(root)]
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="template_collection",
            source_artifact=None,
            source_schema_version="template_registry_record.v1",
            content={
                "schema_version": "mcp_template_collection.v1",
                "templates": records,
                "count": len(records),
            },
            metadata={},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="allowed",
            artifact_type="template_collection",
        )
        return envelope
    if resource["kind"] == "template_detail":
        template_id = resource["template_id"]
        template_detail = load_template(template_id, root)
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="template_detail",
            source_artifact=template_detail.bundle_path,
            source_schema_version=template_detail.template_schema_version,
            content=template_detail.model_dump(mode="json"),
            metadata={"template_id": template_id},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="allowed",
            artifact_type="template_detail",
        )
        return envelope
    if resource["kind"] == "skill_collection":
        records = [skill.model_dump(mode="json") for skill in list_skills(root)]
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="skill_collection",
            source_artifact=None,
            source_schema_version="skill_registry_record.v1",
            content={
                "schema_version": "mcp_skill_collection.v1",
                "skills": records,
                "count": len(records),
            },
            metadata={},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="allowed",
            artifact_type="skill_collection",
        )
        return envelope
    if resource["kind"] == "skill_detail":
        skill_id = resource["skill_id"]
        skill_detail = load_skill_detail(skill_id, root)
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="skill_detail",
            source_artifact=skill_detail.source,
            source_schema_version=skill_detail.schema_version,
            content=skill_detail.model_dump(mode="json"),
            metadata={"skill_id": skill_id},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="allowed",
            artifact_type="skill_detail",
        )
        return envelope
    if resource["kind"] == "policy_summary":
        target_profile = resource["profile"]
        try:
            policy, schema_evidence = load_policy_with_schema_evidence(root, target_profile)
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
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="policy_summary",
            source_artifact=f"policies/{target_profile}.json",
            source_schema_version=schema_evidence["effective"],
            content=_policy_summary(policy),
            metadata={"profile": target_profile},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            result="allowed",
            artifact_type="policy_summary",
        )
        return envelope
    run_id = resource["run_id"]
    resource_name = resource["resource_name"]
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
    envelope = _allowed_envelope(
        uri,
        profile,
        resource_type=resource_type,
        source_artifact=_safe_project_relative(root, store.run_dir / relative),
        source_schema_version=content.get("schema_version"),
        content=content,
        metadata={"run_id": run_id},
    )
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


def _parse_resource_uri(uri: str) -> dict[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "agent-harness":
        raise ValueError("unsupported_uri_scheme")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("query_or_fragment_not_allowed")
    if parsed.netloc == "templates":
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return {"kind": "template_collection"}
        if len(parts) == 1 and RESOURCE_ID_PATTERN.fullmatch(parts[0]) is not None:
            return {"kind": "template_detail", "template_id": parts[0]}
        raise ValueError("unknown_resource")
    if parsed.netloc == "skills":
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return {"kind": "skill_collection"}
        if len(parts) == 1 and RESOURCE_ID_PATTERN.fullmatch(parts[0]) is not None:
            return {"kind": "skill_detail", "skill_id": parts[0]}
        raise ValueError("unknown_resource")
    if parsed.netloc == "policies":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 1 and RESOURCE_ID_PATTERN.fullmatch(parts[0]) is not None:
            return {"kind": "policy_summary", "profile": parts[0]}
        raise ValueError("unknown_resource")
    if parsed.netloc != "runs":
        raise ValueError("unknown_resource")
    parts = parsed.path.lstrip("/").split("/")
    if len(parts) != 2:
        raise ValueError("unknown_resource")
    run_id, resource_name = parts
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("unsafe_run_id")
    if resource_name not in {"summary", "context"}:
        raise ValueError("unknown_resource")
    return {"kind": "run_resource", "run_id": run_id, "resource_name": resource_name}


def _allowed_envelope(
    uri: str,
    profile: str,
    *,
    resource_type: str,
    source_artifact: str | None,
    source_schema_version: object,
    content: object,
    metadata: dict[str, object],
) -> dict[str, Any]:
    return {
        "schema_version": "mcp_resource_envelope.v1",
        "uri": uri,
        "mime_type": "application/json",
        "resource_type": resource_type,
        "source_artifact": source_artifact,
        "source_schema_version": source_schema_version,
        "policy_profile": profile,
        "policy_decision_id": None,
        "redaction_applied": False,
        "denial_status": "allowed",
        "content": content,
        "metadata": metadata,
    }


def _policy_summary(policy: Any) -> dict[str, Any]:
    return {
        "schema_version": "mcp_policy_summary.v1",
        "name": policy.name,
        "description": policy.description,
        "profile_kind": policy.profile_kind,
        "documented": policy.documented,
        "deliberate_selection_required": policy.deliberate_selection_required,
        "allowed_tools": list(policy.allowed_tools),
        "approval_required_tools": list(policy.approval_required_tools),
        "allow_network": policy.allow_network,
        "allowed_context_classes": list(policy.allowed_context_classes),
        "security_fail_threshold": policy.security_fail_threshold,
        "template_capabilities": (
            policy.template_capabilities.model_dump(mode="json")
            if policy.template_capabilities is not None
            else None
        ),
        "provider_trust_policy": dict(policy.provider_trust_policy),
        "provider_input_policy": dict(policy.provider_input_policy),
        "hard_deny_sensitivities": list(policy.hard_deny_sensitivities),
    }


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
