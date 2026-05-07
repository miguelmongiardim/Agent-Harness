from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from pydantic import ValidationError

from agent_harness.config import load_mapping
from agent_harness.skills.schema import (
    SkillRequestedBy,
    SkillResolutionRecord,
    SkillResolutionReport,
)
from agent_harness.skills.validation import load_skill_detail
from agent_harness.storage.schema import WorkspaceMetadata
from agent_harness.tasks.schema import TaskSpec


def resolve_task_skills(task_path: Path, project_root: Path | None = None) -> SkillResolutionReport:
    root = project_root or Path.cwd()
    resolved_task_path = task_path.resolve()
    task = TaskSpec.model_validate(load_mapping(resolved_task_path))
    task_reference = _display_path(root, resolved_task_path)
    requested = _requested_skill_map(task, task_reference)
    _merge_template_recommendations(requested, root)
    records = [
        _resolve_skill(skill_id, requested_by, root) for skill_id, requested_by in requested.items()
    ]
    diagnostics = [diagnostic for record in records for diagnostic in record.diagnostics]
    required_failures = [
        record for record in records if record.required and record.resolution_status != "resolved"
    ]
    return SkillResolutionReport(
        status="failed" if required_failures else "passed",
        task_id=task.task_id,
        task_path=task_reference,
        skills=records,
        diagnostics=diagnostics,
        authority={
            "policy_profile": task.policy_profile,
            "provider_profile": task.provider_profile,
            "allowed_tools": task.allowed_tools,
            "tool_changes": [],
            "approval_changes": [],
            "policy_changes": [],
            "provider_changes": [],
        },
    )


def _requested_skill_map(
    task: TaskSpec,
    task_reference: str,
) -> OrderedDict[str, list[SkillRequestedBy]]:
    requested: OrderedDict[str, list[SkillRequestedBy]] = OrderedDict()
    for skill_id in task.skills:
        requested.setdefault(skill_id, []).append(
            SkillRequestedBy(
                kind="task",
                reference=task_reference,
                field="skills",
                required=True,
            )
        )
    return requested


def _merge_template_recommendations(
    requested: OrderedDict[str, list[SkillRequestedBy]],
    project_root: Path,
) -> None:
    workspace_path = project_root / ".agent-harness" / "workspace.json"
    if not workspace_path.is_file():
        return
    workspace = WorkspaceMetadata.model_validate_json(workspace_path.read_text(encoding="utf-8"))
    for recommendation in workspace.skill_recommendations:
        requested.setdefault(recommendation.skill_id, []).append(
            SkillRequestedBy(
                kind="template",
                reference=f"{recommendation.template_id}@{recommendation.template_version}",
                field="recommended_skills",
                required=False,
            )
        )


def _resolve_skill(
    skill_id: str,
    requested_by: list[SkillRequestedBy],
    project_root: Path,
) -> SkillResolutionRecord:
    required = any(request.required for request in requested_by)
    try:
        detail = load_skill_detail(skill_id, project_root)
    except FileNotFoundError:
        rule_id = "unknown_skill" if required else "missing_recommended_skill"
        severity = "error" if required else "warning"
        return SkillResolutionRecord(
            skill_id=skill_id,
            resolution_status="missing",
            required=required,
            requested_by=requested_by,
            diagnostics=[
                _diagnostic(
                    rule_id,
                    f"skill not found: {skill_id}",
                    "skills",
                    severity=severity,
                )
            ],
        )
    except ValidationError as exc:
        return SkillResolutionRecord(
            skill_id=skill_id,
            resolution_status="invalid",
            required=required,
            requested_by=requested_by,
            diagnostics=[
                _diagnostic(
                    "invalid_skill_resolution",
                    f"skill could not be resolved: {exc}",
                    "skills",
                )
            ],
        )

    return SkillResolutionRecord(
        skill_id=detail.skill_id,
        resolution_status="resolved" if detail.validation_status == "passed" else "invalid",
        required=required,
        requested_by=requested_by,
        version=detail.version,
        source_type=detail.source_type,
        source=detail.source,
        compatibility_status=detail.compatibility_status,
        validation_status=detail.validation_status,
        skill_hash=detail.skill_hash,
        diagnostics=detail.diagnostics,
    )


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _diagnostic(
    rule_id: str,
    message: str,
    location: str,
    *,
    severity: str = "error",
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "location": location,
    }
