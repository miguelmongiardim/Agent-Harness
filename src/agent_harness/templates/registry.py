from __future__ import annotations

import json
import sqlite3
import tomllib
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.templates.schema import TemplateDetail, TemplateRegistryRecord, TemplateSpec
from agent_harness.templates.store import (
    bundled_template_source,
    load_template_spec,
    registry_path,
)


def list_templates(project_root: Path | None = None) -> list[TemplateRegistryRecord]:
    root = project_root or Path.cwd()
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
    records.extend(_unregistered_bundled_pack_records(records))
    records.extend(_local_template_records(root))
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


def _unregistered_bundled_pack_records(
    existing_records: list[TemplateRegistryRecord],
) -> list[TemplateRegistryRecord]:
    existing_ids = {record.template_id for record in existing_records}
    records: list[TemplateRegistryRecord] = []
    for template_id in _iter_bundled_pack_ids():
        if template_id in existing_ids:
            continue
        record = TemplateRegistryRecord(
            template_id=template_id,
            version="",
            title=template_id,
            description="",
            bundle_path=f"bundled_templates/{template_id}/template.v2.toml",
            source_type="bundled_pack",
        )
        records.append(_record_with_source_metadata(record))
    return records


def _iter_bundled_pack_ids() -> list[str]:
    template_ids = []
    for child in _bundled_templates_root().iterdir():
        if child.is_dir():
            manifest = child.joinpath("template.v2.toml")
            if manifest.is_file():
                template_ids.append(child.name)
    return sorted(template_ids)


def _bundled_templates_root() -> Traversable:
    from agent_harness.templates.store import bundled_templates_root

    return bundled_templates_root()


def _local_template_records(project_root: Path) -> list[TemplateRegistryRecord]:
    config = load_config(project_root)
    records: list[TemplateRegistryRecord] = []
    for configured_dir in config.templates.local_dirs:
        local_dir = project_root / configured_dir
        if not local_dir.is_dir():
            continue
        for manifest in sorted(local_dir.glob("*/template.v2.toml")):
            relative_manifest = manifest.relative_to(project_root).as_posix()
            raw = _read_local_pack_manifest(manifest)
            record = TemplateRegistryRecord(
                template_id=_manifest_string(raw, "template_id", manifest.parent.name),
                version=_manifest_string(raw, "version", ""),
                title=_manifest_string(raw, "title", manifest.parent.name),
                description=_manifest_string(raw, "description", ""),
                bundle_path=relative_manifest,
                source_type="local_pack",
            )
            try:
                spec = load_template_spec(record, project_root)
            except Exception:
                records.append(record.model_copy(update={"compatibility_status": "incompatible"}))
            else:
                records.append(
                    record.model_copy(
                        update={
                            "template_id": spec.name,
                            "version": spec.version,
                            "title": spec.title,
                            "description": spec.description,
                            "compatibility_status": _compatibility_status(spec),
                        }
                    )
                )
    return records


def _read_local_pack_manifest(manifest: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def _manifest_string(raw: dict[str, Any], field: str, fallback: str) -> str:
    value = raw.get(field)
    return value if isinstance(value, str) else fallback


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


def load_template(name: str, project_root: Path | None = None) -> TemplateDetail:
    root = project_root or Path.cwd()
    record = load_template_record(name, root)
    if record.source_type == "local_pack":
        _ensure_local_template_pack_usable(record, root)
    spec = load_template_spec(record, root)
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
        recommended_skills=spec.recommended_skills,
        files=spec.files,
    )


def load_template_record(
    name: str,
    project_root: Path | None = None,
) -> TemplateRegistryRecord:
    for record in list_templates(project_root):
        if record.template_id == name:
            return record
    raise FileNotFoundError(f"template not found: {name}")


def _ensure_local_template_pack_usable(
    record: TemplateRegistryRecord,
    project_root: Path,
) -> None:
    from agent_harness.templates.validation import validate_template_pack_path

    report = validate_template_pack_path(project_root / Path(record.bundle_path).parent)
    if report["status"] != "passed":
        raise ValueError("template pack validation failed")
