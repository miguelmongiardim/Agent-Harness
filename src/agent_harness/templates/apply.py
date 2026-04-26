from __future__ import annotations

import difflib
from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    TemplateApplyRecord,
    TemplateDetail,
    TemplateProposedWrite,
    ToolCall,
)
from agent_harness.utils import sha256_text, stable_id


def plan_template_apply(
    spec: TemplateDetail,
    destination: Path,
    policy: PolicyEngine,
    force: bool = False,
) -> TemplateApplyRecord:
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
                raise FileExistsError(
                    f"template apply would overwrite existing file: {policy_path}"
                )
            before = target.read_text(encoding="utf-8")
        else:
            before = ""
        writes.append(
            TemplateProposedWrite(
                path=policy_path,
                before_hash=sha256_text(before),
                after_hash=sha256_text(file.content),
                diff=_diff(before, file.content, policy_path),
                proposed_content=file.content,
            )
        )
    return TemplateApplyRecord(
        template_id=spec.template_id,
        version=spec.version,
        title=spec.title,
        description=spec.description,
        destination=destination_path,
        proposed_writes=writes,
        force=force,
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
