from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_harness.config import load_config
from agent_harness.mcp.access_log import append_mcp_access_log
from agent_harness.mcp.schema import (
    McpResourceDescriptor,
    McpResourceEnvelope,
    McpResourceList,
)
from agent_harness.orchestration.store import OrchestrationStore
from agent_harness.policy import PolicyError, load_policy, load_policy_with_schema_evidence
from agent_harness.skills import list_skills, load_skill_detail
from agent_harness.storage import RunStore
from agent_harness.templates import list_templates, load_template

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ORCHESTRATION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
ORCHESTRATION_MUTATION_RESOURCES = {"approve", "resume", "run"}


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
    orchestrations_root = artifact_root / "orchestrations"
    if orchestrations_root.exists():
        resources.append(
            {
                "uri": "agent-harness://orchestrations",
                "resource_type": "orchestration_collection",
                "mime_type": "application/json",
                "name": "orchestrations",
                "description": "Available Agent Harness orchestrations.",
            }
        )
        for orchestration_dir in sorted(orchestrations_root.iterdir()):
            if (
                not orchestration_dir.is_dir()
                or ORCHESTRATION_ID_PATTERN.fullmatch(orchestration_dir.name) is None
            ):
                continue
            if (orchestration_dir / "summary.json").exists():
                resources.append(
                    _orchestration_resource_descriptor(
                        root,
                        orchestration_dir.name,
                        "summary",
                        "orchestration_summary",
                        orchestration_dir / "summary.json",
                    )
                )
                resources.append(
                    _orchestration_resource_descriptor(
                        root,
                        orchestration_dir.name,
                        "children",
                        "orchestration_children",
                        orchestration_dir / "summary.json",
                    )
                )
            if (orchestration_dir / "manifest.json").exists():
                resources.append(
                    _orchestration_resource_descriptor(
                        root,
                        orchestration_dir.name,
                        "manifest",
                        "orchestration_manifest",
                        orchestration_dir / "manifest.json",
                    )
                )
            if (orchestration_dir / "events.jsonl").exists():
                resources.append(
                    _orchestration_resource_descriptor(
                        root,
                        orchestration_dir.name,
                        "events",
                        "orchestration_events",
                        orchestration_dir / "events.jsonl",
                    )
                )
            if (orchestration_dir / "handoffs").exists():
                resources.append(
                    _orchestration_resource_descriptor(
                        root,
                        orchestration_dir.name,
                        "handoffs",
                        "orchestration_handoffs",
                        orchestration_dir / "handoffs",
                    )
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
            if (run_dir / "provider_calls.json").exists():
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "provider-evidence",
                        "run_provider_evidence",
                        run_dir / "provider_calls.json",
                    )
                )
            if (run_dir / "events.jsonl").exists():
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "events",
                        "run_events",
                        run_dir / "events.jsonl",
                    )
                )
            if any((run_dir / "actions").glob("*.json")):
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "tools",
                        "run_tools",
                        run_dir / "actions",
                    )
                )
            if any((run_dir / "approvals").glob("*.json")):
                resources.append(
                    _resource_descriptor(
                        root,
                        run_dir.name,
                        "approvals",
                        "run_approvals",
                        run_dir / "approvals",
                    )
                )
            for resource_name, resource_type, relative in (
                ("security-findings", "run_security_findings", "security_findings.json"),
                ("eval", "run_eval_results", "eval_results.json"),
                ("retrieval-scorecard", "run_retrieval_scorecard", "retrieval_scorecards.json"),
            ):
                artifact_path = run_dir / relative
                if artifact_path.exists():
                    resources.append(
                        _resource_descriptor(
                            root,
                            run_dir.name,
                            resource_name,
                            resource_type,
                            artifact_path,
                        )
                    )
    resource_models = [McpResourceDescriptor.model_validate(resource) for resource in resources]
    return McpResourceList(
        profile=profile,
        resources=resource_models,
        count=len(resource_models),
    ).model_dump(mode="json", exclude_none=True)


def read_mcp_resource(
    project_root: Path,
    uri: str,
    profile: str = "default",
    *,
    transport: str = "cli",
) -> dict[str, Any]:
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
            transport=transport,
            result="denied",
            orchestration_id=_safe_orchestration_id_from_uri(uri),
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
            transport=transport,
            result="denied",
            orchestration_id=_safe_orchestration_id_from_uri(uri),
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
            transport=transport,
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
            transport=transport,
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
            transport=transport,
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
            transport=transport,
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
                transport=transport,
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
            transport=transport,
            result="allowed",
            artifact_type="policy_summary",
        )
        return envelope
    if resource["kind"] == "orchestration_collection":
        orchestration_records = _orchestration_collection_records(root, artifact_root)
        envelope = _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_collection",
            source_artifact=None,
            source_schema_version="orchestration_summary.v1",
            content={
                "schema_version": "mcp_orchestration_collection.v1",
                "orchestrations": orchestration_records,
                "count": len(orchestration_records),
            },
            metadata={},
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result="allowed",
            artifact_type="orchestration_collection",
        )
        return envelope
    if resource["kind"] == "orchestration_resource":
        orchestration_id = resource["orchestration_id"]
        resource_name = resource["resource_name"]
        orchestration_store = OrchestrationStore.open_existing(
            root,
            artifact_root,
            orchestration_id,
        )
        envelope = _orchestration_resource_envelope(
            root,
            orchestration_store,
            uri,
            profile,
            resource_name,
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result="allowed",
            orchestration_id=orchestration_id,
            artifact_type=envelope["resource_type"],
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
    elif resource_name == "provider-evidence":
        envelope = _provider_evidence_envelope(root, artifact_root, store, uri, profile)
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result=_access_result(envelope),
            run_id=run_id,
            artifact_type="run_provider_evidence",
        )
        return envelope
    elif resource_name == "events":
        envelope = _events_envelope(root, store, uri, profile)
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result=_access_result(envelope),
            run_id=run_id,
            artifact_type="run_events",
        )
        return envelope
    elif resource_name == "tools":
        envelope = _directory_json_envelope(
            root,
            store,
            uri,
            profile,
            directory="actions",
            resource_type="run_tools",
            content_schema="mcp_run_tools.v1",
            content_key="actions",
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result=_access_result(envelope),
            run_id=run_id,
            artifact_type="run_tools",
        )
        return envelope
    elif resource_name == "approvals":
        envelope = _directory_json_envelope(
            root,
            store,
            uri,
            profile,
            directory="approvals",
            resource_type="run_approvals",
            content_schema="mcp_run_approvals.v1",
            content_key="approvals",
        )
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result=_access_result(envelope),
            run_id=run_id,
            artifact_type="run_approvals",
        )
        return envelope
    elif resource_name in {"security-findings", "eval", "retrieval-scorecard"}:
        relative, resource_type = {
            "security-findings": ("security_findings.json", "run_security_findings"),
            "eval": ("eval_results.json", "run_eval_results"),
            "retrieval-scorecard": ("retrieval_scorecards.json", "run_retrieval_scorecard"),
        }[resource_name]
        envelope = _json_artifact_envelope(root, store, uri, profile, relative, resource_type)
        _append_access_log(
            artifact_root,
            uri=uri,
            profile=profile,
            transport=transport,
            result=_access_result(envelope),
            run_id=run_id,
            artifact_type=resource_type,
        )
        return envelope
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
        transport=transport,
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
    return McpResourceDescriptor(
        uri=f"agent-harness://runs/{run_id}/{name}",
        resource_type=resource_type,
        mime_type="application/json",
        name=f"{run_id}/{name}",
        source_artifact=_safe_project_relative(project_root, artifact_path),
    ).model_dump(mode="json", exclude_none=True)


def _orchestration_resource_descriptor(
    project_root: Path,
    orchestration_id: str,
    name: str,
    resource_type: str,
    artifact_path: Path,
) -> dict[str, str]:
    return McpResourceDescriptor(
        uri=f"agent-harness://orchestrations/{orchestration_id}/{name}",
        resource_type=resource_type,
        mime_type="application/json",
        name=f"{orchestration_id}/{name}",
        source_artifact=_safe_project_relative(project_root, artifact_path),
    ).model_dump(mode="json", exclude_none=True)


def _orchestration_collection_records(
    project_root: Path,
    artifact_root: Path,
) -> list[dict[str, str]]:
    orchestrations_root = artifact_root / "orchestrations"
    if not orchestrations_root.exists():
        return []
    records: list[dict[str, str]] = []
    for orchestration_dir in sorted(orchestrations_root.iterdir()):
        summary_path = orchestration_dir / "summary.json"
        if (
            not orchestration_dir.is_dir()
            or ORCHESTRATION_ID_PATTERN.fullmatch(orchestration_dir.name) is None
            or not summary_path.exists()
        ):
            continue
        records.append(
            {
                "orchestration_id": orchestration_dir.name,
                "summary_resource": (
                    f"agent-harness://orchestrations/{orchestration_dir.name}/summary"
                ),
                "source_artifact": _safe_project_relative(project_root, summary_path),
            }
        )
    return records


def _orchestration_resource_envelope(
    project_root: Path,
    store: OrchestrationStore,
    uri: str,
    profile: str,
    resource_name: str,
) -> dict[str, Any]:
    metadata: dict[str, object] = {"orchestration_id": store.orchestration_id}
    if resource_name == "summary":
        content = store.read_data("summary.json")
        return _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_summary",
            source_artifact=_safe_project_relative(
                project_root,
                store.orchestration_dir / "summary.json",
            ),
            source_schema_version=content.get("schema_version"),
            content=content,
            metadata=metadata,
        )
    if resource_name == "manifest":
        content = store.read_data("manifest.json")
        return _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_manifest",
            source_artifact=_safe_project_relative(
                project_root,
                store.orchestration_dir / "manifest.json",
            ),
            source_schema_version=content.get("schema_version"),
            content=content,
            metadata=metadata,
        )
    if resource_name == "events":
        events = store.events()
        return _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_events",
            source_artifact=_safe_project_relative(project_root, store.events_path),
            source_schema_version="orchestration_event.v1",
            content={
                "schema_version": "mcp_orchestration_events.v1",
                "orchestration_id": store.orchestration_id,
                "events": events,
                "count": len(events),
            },
            metadata=metadata,
        )
    if resource_name == "children":
        summary = store.read_data("summary.json")
        children = summary.get("children", [])
        if not isinstance(children, list):
            children = []
        return _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_children",
            source_artifact=_safe_project_relative(
                project_root,
                store.orchestration_dir / "summary.json",
            ),
            source_schema_version=summary.get("schema_version"),
            content={
                "schema_version": "mcp_orchestration_children.v1",
                "orchestration_id": store.orchestration_id,
                "children": children,
                "count": len(children),
            },
            metadata=metadata,
        )
    if resource_name == "handoffs":
        handoffs = store.read_handoffs()
        return _allowed_envelope(
            uri,
            profile,
            resource_type="orchestration_handoffs",
            source_artifact=_safe_project_relative(
                project_root,
                store.orchestration_dir / "handoffs",
            ),
            source_schema_version="orchestration_handoff.v1",
            content={
                "schema_version": "mcp_orchestration_handoffs.v1",
                "orchestration_id": store.orchestration_id,
                "handoffs": handoffs,
                "count": len(handoffs),
            },
            metadata=metadata,
        )
    raise ValueError(f"unsupported MCP orchestration resource: {resource_name}")


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
    if parsed.netloc == "orchestrations":
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return {"kind": "orchestration_collection"}
        if len(parts) != 2:
            raise ValueError("unknown_resource")
        orchestration_id, resource_name = parts
        if ORCHESTRATION_ID_PATTERN.fullmatch(orchestration_id) is None:
            raise ValueError("unsafe_orchestration_id")
        if resource_name in ORCHESTRATION_MUTATION_RESOURCES:
            raise ValueError("unsupported_orchestration_mutation")
        if resource_name not in {"summary", "manifest", "events", "children", "handoffs"}:
            raise ValueError("unknown_resource")
        return {
            "kind": "orchestration_resource",
            "orchestration_id": orchestration_id,
            "resource_name": resource_name,
        }
    if parsed.netloc != "runs":
        raise ValueError("unknown_resource")
    parts = parsed.path.lstrip("/").split("/")
    if len(parts) != 2:
        raise ValueError("unknown_resource")
    run_id, resource_name = parts
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError("unsafe_run_id")
    if resource_name not in {
        "summary",
        "context",
        "provider-evidence",
        "events",
        "tools",
        "approvals",
        "security-findings",
        "eval",
        "retrieval-scorecard",
    }:
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
    return McpResourceEnvelope(
        uri=uri,
        resource_type=resource_type,
        source_artifact=source_artifact,
        source_schema_version=source_schema_version,
        policy_profile=profile,
        denial_status="allowed",
        content=content,
        metadata=metadata,
    ).model_dump(mode="json")


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


def _provider_evidence_envelope(
    project_root: Path,
    artifact_root: Path,
    store: RunStore,
    uri: str,
    profile: str,
) -> dict[str, Any]:
    try:
        provider_calls = store.read_data("provider_calls.json")
    except FileNotFoundError:
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="provider_calls.json",
            artifact_type="run_provider_evidence",
            status="missing",
        )
    except (json.JSONDecodeError, ValueError):
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="provider_calls.json",
            artifact_type="run_provider_evidence",
            status="malformed",
        )
    try:
        provider = _read_optional_data(store, "provider.json")
    except (json.JSONDecodeError, ValueError):
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="provider.json",
            artifact_type="run_provider_evidence",
            status="malformed",
        )
    try:
        provider_input = _read_optional_data(store, "provider_input.json")
    except (json.JSONDecodeError, ValueError):
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="provider_input.json",
            artifact_type="run_provider_evidence",
            status="malformed",
        )
    content = {
        "schema_version": "mcp_provider_evidence.v1",
        "run_id": store.run_id,
        "provider": provider,
        "provider_input": _provider_input_summary(provider_input),
        "calls": [_provider_call_summary(call) for call in provider_calls.get("calls", [])],
        "call_count": len(provider_calls.get("calls", [])),
    }
    return _allowed_envelope(
        uri,
        profile,
        resource_type="run_provider_evidence",
        source_artifact=_safe_project_relative(
            project_root,
            artifact_root / "runs" / store.run_id / "provider_calls.json",
        ),
        source_schema_version=provider_calls.get("schema_version"),
        content=content,
        metadata={"run_id": store.run_id},
    )


def _events_envelope(
    project_root: Path,
    store: RunStore,
    uri: str,
    profile: str,
) -> dict[str, Any]:
    if not store.events_path.exists():
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="events.jsonl",
            artifact_type="run_events",
            status="missing",
        )
    try:
        events = store.events()
    except json.JSONDecodeError:
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative="events.jsonl",
            artifact_type="run_events",
            status="malformed",
        )
    return _allowed_envelope(
        uri,
        profile,
        resource_type="run_events",
        source_artifact=_safe_project_relative(project_root, store.events_path),
        source_schema_version="run_event.v1",
        content={
            "schema_version": "mcp_run_events.v1",
            "run_id": store.run_id,
            "events": events,
            "count": len(events),
        },
        metadata={"run_id": store.run_id},
    )


def _directory_json_envelope(
    project_root: Path,
    store: RunStore,
    uri: str,
    profile: str,
    *,
    directory: str,
    resource_type: str,
    content_schema: str,
    content_key: str,
) -> dict[str, Any]:
    directory_path = store.run_dir / directory
    if not directory_path.exists():
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative=directory,
            artifact_type=resource_type,
            status="missing",
        )
    try:
        items = [
            store.read_data(f"{directory}/{path.name}")
            for path in sorted(directory_path.glob("*.json"))
        ]
    except (json.JSONDecodeError, ValueError):
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative=directory,
            artifact_type=resource_type,
            status="malformed",
        )
    return _allowed_envelope(
        uri,
        profile,
        resource_type=resource_type,
        source_artifact=_safe_project_relative(project_root, directory_path),
        source_schema_version=None,
        content={
            "schema_version": content_schema,
            "run_id": store.run_id,
            content_key: items,
            "count": len(items),
        },
        metadata={"run_id": store.run_id},
    )


def _json_artifact_envelope(
    project_root: Path,
    store: RunStore,
    uri: str,
    profile: str,
    relative: str,
    resource_type: str,
) -> dict[str, Any]:
    try:
        content = store.read_data(relative)
    except FileNotFoundError:
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative=relative,
            artifact_type=resource_type,
            status="missing",
        )
    except (json.JSONDecodeError, ValueError):
        return _artifact_status_envelope(
            project_root,
            store,
            uri,
            profile,
            relative=relative,
            artifact_type=resource_type,
            status="malformed",
        )
    return _allowed_envelope(
        uri,
        profile,
        resource_type=resource_type,
        source_artifact=_safe_project_relative(project_root, store.run_dir / relative),
        source_schema_version=content.get("schema_version"),
        content=content,
        metadata={"run_id": store.run_id},
    )


def _artifact_status_envelope(
    project_root: Path,
    store: RunStore,
    uri: str,
    profile: str,
    *,
    relative: str,
    artifact_type: str,
    status: str,
) -> dict[str, Any]:
    detail = f"run artifact is {status}"
    return _allowed_envelope(
        uri,
        profile,
        resource_type=f"{status}_artifact",
        source_artifact=_safe_project_relative(project_root, store.run_dir / relative),
        source_schema_version=None,
        content={
            "schema_version": "mcp_artifact_status.v1",
            "status": status,
            "artifact_type": artifact_type,
            "detail": detail,
        },
        metadata={"run_id": store.run_id},
    )


def _access_result(envelope: dict[str, Any]) -> str:
    content = envelope.get("content")
    if isinstance(content, dict) and content.get("schema_version") == "mcp_artifact_status.v1":
        status = content.get("status")
        if isinstance(status, str):
            return status
    return "allowed"


def _provider_call_summary(call: object) -> dict[str, Any]:
    if not isinstance(call, dict):
        return {"schema_version": "mcp_provider_call_summary.v1", "malformed": True}
    allowed_fields = {
        "audit_id",
        "run_id",
        "task_id",
        "provider_profile_id",
        "transport",
        "trust_zone",
        "model",
        "endpoint_identity",
        "network",
        "phase",
        "mode",
        "fixture_id",
        "approval_ids",
        "action_count",
        "actions_hash",
        "provider_input_hash",
        "action_envelope_hash",
        "checkpoint_hash",
        "prompt_hash",
        "response_hash",
        "redacted_prompt_artifact",
        "redacted_response_artifact",
        "redacted_prompt_summary",
        "redacted_response_summary",
        "latency_ms",
        "token_metrics",
        "policy_decision_ids",
        "created_at",
    }
    summary = {
        key: value
        for key, value in call.items()
        if key in allowed_fields and key not in {"raw_request", "raw_response"}
    }
    summary["schema_version"] = "mcp_provider_call_summary.v1"
    return summary


def _provider_input_summary(provider_input: dict[str, Any] | None) -> dict[str, Any] | None:
    if provider_input is None:
        return None
    raw_records = provider_input.get("records", [])
    records = raw_records if isinstance(raw_records, list) else []
    included_records = [
        record for record in records if isinstance(record, dict) and record.get("included")
    ]
    policy_decision_ids = sorted(
        {
            record["policy_decision_id"]
            for record in records
            if isinstance(record, dict) and isinstance(record.get("policy_decision_id"), str)
        }
    )
    return {
        "schema_version": "mcp_provider_input_summary.v1",
        "run_id": provider_input.get("run_id"),
        "task_id": provider_input.get("task_id"),
        "provider_profile_id": provider_input.get("provider_profile_id"),
        "trust_zone": provider_input.get("trust_zone"),
        "record_count": len(records),
        "included_count": len(included_records),
        "policy_decision_ids": policy_decision_ids,
    }


def _read_optional_data(store: RunStore, relative: str) -> dict[str, Any] | None:
    if not (store.run_dir / relative).exists():
        return None
    return store.read_data(relative)


def _denial_envelope(uri: str, profile: str, reason: str) -> dict[str, Any]:
    return McpResourceEnvelope(
        uri=uri,
        resource_type="denial",
        source_artifact=None,
        source_schema_version=None,
        policy_profile=profile,
        denial_status="denied",
        content=None,
        metadata={"denial_reason": reason},
    ).model_dump(mode="json")


def _safe_orchestration_id_from_uri(uri: str) -> str | None:
    parsed = urlparse(uri)
    if parsed.scheme != "agent-harness" or parsed.netloc != "orchestrations":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts or ORCHESTRATION_ID_PATTERN.fullmatch(parts[0]) is None:
        return None
    return parts[0]


def _append_access_log(
    artifact_root: Path,
    *,
    uri: str,
    profile: str,
    result: str,
    transport: str = "cli",
    run_id: str | None = None,
    orchestration_id: str | None = None,
    artifact_type: str | None = None,
    denial_reason: str | None = None,
) -> None:
    append_mcp_access_log(
        artifact_root,
        request_type="resource_read",
        uri=uri,
        profile=profile,
        transport=transport,
        result=result,
        run_id=run_id,
        orchestration_id=orchestration_id,
        artifact_type=artifact_type,
        denial_reason=denial_reason,
    )


def _safe_project_relative(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()
