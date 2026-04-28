from __future__ import annotations

from typing import Literal

from agent_harness.schemas import (
    ContextManifest,
    ContextManifestItem,
    SkillManifest,
    SkillManifestRecord,
    SkillResolutionRecord,
    SkillResolutionReport,
)


def build_skill_manifest(
    run_id: str,
    task_id: str,
    resolution: SkillResolutionReport,
    context_manifest: ContextManifest,
) -> SkillManifest | None:
    records = [
        _record_from_resolution(record, context_manifest)
        for record in resolution.skills
        if _should_record_skill(record, context_manifest)
    ]
    if not records:
        return None
    return SkillManifest(
        run_id=run_id,
        task_id=task_id,
        context_manifest_id=context_manifest.manifest_id,
        skills=records,
    )


def _should_record_skill(
    record: SkillResolutionRecord,
    context_manifest: ContextManifest,
) -> bool:
    if record.required:
        return True
    return _find_skill_item(record.skill_id, context_manifest) is not None


def _record_from_resolution(
    record: SkillResolutionRecord,
    context_manifest: ContextManifest,
) -> SkillManifestRecord:
    item = _find_skill_item(record.skill_id, context_manifest)
    inclusion_status: Literal["included", "rejected", "not_included"] = "not_included"
    if item is not None:
        inclusion_status = "included" if item.policy_allowed else "rejected"
    return SkillManifestRecord(
        skill_id=record.skill_id,
        version=record.version or (item.skill_version if item is not None else None),
        source_type=record.source_type,
        source=record.source or (item.skill_source if item is not None else None),
        skill_hash=record.skill_hash or (item.skill_hash if item is not None else None),
        required=record.required,
        requested_by=record.requested_by,
        resolution_status=record.resolution_status,
        inclusion_status=inclusion_status,
        policy_decision_id=item.policy_decision_id if item is not None else None,
        context_manifest_id=context_manifest.manifest_id,
        context_manifest_item_id=item.item_id if item is not None else None,
        diagnostics=record.diagnostics,
    )


def _find_skill_item(
    skill_id: str,
    context_manifest: ContextManifest,
) -> ContextManifestItem | None:
    for item in [*context_manifest.items, *context_manifest.rejected_items]:
        if item.source_kind == "skill" and item.skill_id == skill_id:
            return item
    return None
