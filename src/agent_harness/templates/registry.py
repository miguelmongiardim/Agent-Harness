from __future__ import annotations

import json
import sqlite3

from agent_harness.schemas import TemplateDetail, TemplateRegistryRecord
from agent_harness.templates.store import load_template_spec, registry_path


def list_templates() -> list[TemplateRegistryRecord]:
    with registry_path() as path, sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            select template_id, version, title, description, bundle_path, tags_json
            from template_registry
            order by template_id
            """
        ).fetchall()
    return [
        TemplateRegistryRecord(
            template_id=template_id,
            version=version,
            title=title,
            description=description,
            bundle_path=bundle_path,
            tags=json.loads(tags_json),
        )
        for template_id, version, title, description, bundle_path, tags_json in rows
    ]


def load_template(name: str) -> TemplateDetail:
    record = load_template_record(name)
    spec = load_template_spec(record)
    return TemplateDetail(
        template_id=record.template_id,
        version=record.version,
        title=record.title,
        description=record.description,
        bundle_path=record.bundle_path,
        tags=record.tags,
        template_schema_version=spec.schema_version,
        minimum_agent_harness_version=spec.minimum_agent_harness_version,
        required_capabilities=spec.required_capabilities,
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
