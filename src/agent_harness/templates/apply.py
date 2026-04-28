from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    TemplateApplyRecord,
    TemplateDetail,
    TemplateProposedWrite,
    ToolCall,
)
from agent_harness.utils import sha256_json, sha256_text, stable_id


@dataclass(frozen=True)
class _TemplateApplicationPlan:
    record: TemplateApplyRecord
    skipped_files: list[str]
    conflicts: list[dict[str, str]]
    rendered_hashes: dict[str, str]


def build_template_application_evidence(
    spec: TemplateDetail,
    destination: Path,
    policy: PolicyEngine,
    *,
    parameters: dict[str, str],
    mode: str,
    status: str = "planned",
    created_files: list[str] | None = None,
    diagnostics: list[dict[str, object]] | None = None,
) -> dict[str, Any]:
    plan = _build_template_application_plan(
        spec,
        destination,
        policy,
        force=False,
        report_existing=True,
    )
    template_apply = plan.record
    planned_files = list(plan.rendered_hashes)
    operation_types = {
        write.path: "create"
        if write.before_hash == sha256_text("")
        else "overwrite"
        for write in template_apply.proposed_writes
    }
    operation_types.update({path: "skip" for path in plan.skipped_files})
    operation_types.update({conflict["path"]: "conflict" for conflict in plan.conflicts})
    plan_payload = {
        "template_id": spec.template_id,
        "template_version": spec.version,
        "target_path": template_apply.destination,
        "parameters": parameters,
        "planned_files": planned_files,
        "operation_types": operation_types,
        "rendered_hashes": plan.rendered_hashes,
        "policy_profile": policy.profile.name,
        "conflicts": plan.conflicts,
        "skipped_files": plan.skipped_files,
    }
    approval_required = bool(plan.conflicts)
    evidence = {
        "schema_version": "template_application.v1",
        "status": status,
        "mode": mode,
        "template_id": spec.template_id,
        "template_version": spec.version,
        "source": {
            "source_type": spec.source_type,
            "bundle_path": spec.bundle_path,
            "compatibility_status": spec.compatibility_status,
        },
        "target_path": template_apply.destination,
        "parameters": parameters,
        "planned_files": planned_files,
        "planned_creates": [
            path for path, operation in operation_types.items() if operation == "create"
        ],
        "created_files": created_files or [],
        "skipped_files": plan.skipped_files,
        "conflicts": plan.conflicts,
        "operation_types": operation_types,
        "rendered_hashes": plan.rendered_hashes,
        "generated_schema_versions": spec.generated_schema_versions,
        "required_capabilities": spec.required_capabilities,
        "warnings": [],
        "policy_implications": [
            {
                "path": write.path,
                "tool_name": "patch_file",
                "operation": operation_types[write.path],
                "approval_required": False,
                "reason": "tool call allowed",
            }
            for write in template_apply.proposed_writes
        ]
        + [
            {
                "path": path,
                "tool_name": "patch_file",
                "operation": "skip",
                "approval_required": False,
                "reason": "target file already matches rendered content",
            }
            for path in plan.skipped_files
        ]
        + [
            {
                "path": conflict["path"],
                "tool_name": "patch_file",
                "operation": "conflict",
                "approval_required": True,
                "reason": conflict["reason"],
            }
            for conflict in plan.conflicts
        ],
        "generated_files": [file.path for file in spec.files],
        "plan_hash": sha256_json(plan_payload),
        "approval_required": approval_required,
        "approval_id": None,
        "policy_profile": policy.profile.name,
        "diagnostics": diagnostics or [],
    }
    if mode == "preview_diff":
        evidence["preview_diffs"] = [
            {"path": write.path, "diff": _redact_preview_diff(policy, write.diff)}
            for write in template_apply.proposed_writes
        ]
    return evidence


def plan_template_apply(
    spec: TemplateDetail,
    destination: Path,
    policy: PolicyEngine,
    force: bool = False,
) -> TemplateApplyRecord:
    return _build_template_application_plan(
        spec,
        destination,
        policy,
        force=force,
        report_existing=False,
    ).record


def _build_template_application_plan(
    spec: TemplateDetail,
    destination: Path,
    policy: PolicyEngine,
    *,
    force: bool,
    report_existing: bool,
) -> _TemplateApplicationPlan:
    unsupported = _unsupported_required_capabilities(spec, policy)
    if unsupported:
        capabilities = ", ".join(unsupported)
        raise PermissionError(
            f"template {spec.template_id} has unsupported template capabilities: {capabilities}"
        )

    try:
        destination_path = destination.resolve().relative_to(policy.project_root).as_posix()
    except ValueError as exc:
        raise PermissionError("template destination outside project root") from exc

    writes: list[TemplateProposedWrite] = []
    skipped_files: list[str] = []
    conflicts: list[dict[str, str]] = []
    rendered_hashes: dict[str, str] = {}
    for file in spec.files:
        target = destination / file.path
        try:
            policy_path = target.resolve().relative_to(policy.project_root).as_posix()
        except ValueError as exc:
            raise PermissionError("template destination outside project root") from exc
        call = ToolCall(
            action_id=stable_id("action", "template", spec.template_id, policy_path),
            tool_name="patch_file",
            arguments={
                "path": policy_path,
                "before_hash": "",
                "proposed_content": file.content,
            },
            reason=f"apply template {spec.template_id}",
        )
        decision = policy.evaluate_tool_call(call, task=None, checkpoint_hash="template_apply")
        if not decision.allowed:
            raise PermissionError(decision.reason)

        if target.exists():
            if not force:
                if report_existing:
                    before = target.read_text(encoding="utf-8")
                    rendered_hashes[policy_path] = sha256_text(file.content)
                    if before == file.content:
                        skipped_files.append(policy_path)
                    else:
                        conflicts.append(
                            {
                                "path": policy_path,
                                "reason": "target file already exists with different content",
                                "before_hash": sha256_text(before),
                                "after_hash": sha256_text(file.content),
                            }
                        )
                    continue
                raise FileExistsError(
                    f"template apply would overwrite existing file: {policy_path}"
                )
            before = target.read_text(encoding="utf-8")
        else:
            before = ""
        rendered_hashes[policy_path] = sha256_text(file.content)
        writes.append(
            TemplateProposedWrite(
                path=policy_path,
                before_hash=sha256_text(before),
                after_hash=sha256_text(file.content),
                diff=_diff(before, file.content, policy_path),
                proposed_content=file.content,
            )
        )
    return _TemplateApplicationPlan(
        record=TemplateApplyRecord(
            template_id=spec.template_id,
            version=spec.version,
            title=spec.title,
            description=spec.description,
            destination=destination_path,
            proposed_writes=writes,
            force=force,
        ),
        skipped_files=skipped_files,
        conflicts=conflicts,
        rendered_hashes=rendered_hashes,
    )


def _unsupported_required_capabilities(spec: TemplateDetail, policy: PolicyEngine) -> list[str]:
    if spec.template_schema_version != "template.v2":
        return []
    capability_policy = policy.profile.template_capabilities
    if capability_policy is None or capability_policy.default_action == "deny":
        allowed = set(capability_policy.allowed_capabilities if capability_policy else [])
        return [
            capability for capability in spec.required_capabilities if capability not in allowed
        ]
    return []


def _diff(before: str, after: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _redact_preview_diff(policy: PolicyEngine, diff: str) -> str:
    redacted, _ = policy.redact_text(diff)
    return redacted
