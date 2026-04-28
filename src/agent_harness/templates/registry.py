from __future__ import annotations

import json
import sqlite3

from agent_harness import __version__
from agent_harness.schemas import TemplateDetail, TemplateRegistryRecord, TemplateSpec
from agent_harness.templates.store import (
    bundled_template_source,
    load_template_spec,
    registry_path,
)


def list_templates() -> list[TemplateRegistryRecord]:
    with registry_path() as path, sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            select template_id, version, title, description, bundle_path, tags_json
            from template_registry
            order by template_id
            """
        ).fetchall()
    records = [
        _record_with_source_metadata(
            TemplateRegistryRecord(
                template_id=template_id,
                version=version,
                title=title,
                description=description,
                bundle_path=bundle_path,
                tags=json.loads(tags_json),
            )
        )
        for template_id, version, title, description, bundle_path, tags_json in rows
    ]
    _ensure_unique_template_ids(records)
    return records


def _record_with_source_metadata(record: TemplateRegistryRecord) -> TemplateRegistryRecord:
    spec = load_template_spec(record)
    source_type, bundle_path = bundled_template_source(record)
    return record.model_copy(
        update={
            "version": spec.version or record.version,
            "title": spec.title or record.title,
            "description": spec.description or record.description,
            "bundle_path": bundle_path,
            "source_type": source_type,
            "compatibility_status": _compatibility_status(spec),
        }
    )


def _ensure_unique_template_ids(records: list[TemplateRegistryRecord]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        if record.template_id in seen:
            duplicates.add(record.template_id)
        seen.add(record.template_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate template ids discovered: {duplicate_list}")


def _compatibility_status(spec: TemplateSpec) -> str:
    minimum = spec.minimum_agent_harness_version
    maximum = spec.maximum_agent_harness_version
    if minimum is not None and _compare_versions(__version__, minimum) < 0:
        return "incompatible"
    if maximum is not None and _compare_versions(__version__, maximum) > 0:
        return "incompatible"
    return "compatible"


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _version_parts(value: str) -> tuple[int, int, int]:
    parts = value.removeprefix("v").split(".")
    parsed = [int(part) for part in parts[:3]]
    while len(parsed) < 3:
        parsed.append(0)
    return (parsed[0], parsed[1], parsed[2])


def load_template(name: str) -> TemplateDetail:
    record = load_template_record(name)
    spec = load_template_spec(record)
    return TemplateDetail(
        template_id=record.template_id,
        version=record.version,
        title=record.title,
        description=record.description,
        bundle_path=record.bundle_path,
        source_type=record.source_type,
        compatibility_status=record.compatibility_status,
        tags=record.tags,
        template_schema_version=spec.schema_version,
        minimum_agent_harness_version=spec.minimum_agent_harness_version,
        maximum_agent_harness_version=spec.maximum_agent_harness_version,
        required_capabilities=spec.required_capabilities,
        parameters=spec.parameters,
        generated_schema_versions=spec.generated_schema_versions,
        provider_requirements=spec.provider_requirements,
        policy_requirements=spec.policy_requirements,
        retrieval_assumptions=spec.retrieval_assumptions,
        eval_or_demo_metadata=spec.eval_or_demo_metadata,
        files=spec.files,
    )


def load_template_record(name: str) -> TemplateRegistryRecord:
    for record in list_templates():
        if record.template_id == name:
            return record
    raise FileNotFoundError(f"template not found: {name}")
