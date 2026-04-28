from __future__ import annotations

import json
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from agent_harness.schemas import TemplateRegistryRecord, TemplateSpec

_BUNDLED_TEMPLATES = resources.files("agent_harness").joinpath("bundled_templates")
_REGISTRY_PATH = _BUNDLED_TEMPLATES.joinpath("registry.sqlite3")


@contextmanager
def registry_path() -> Iterator[Path]:
    with resources.as_file(_REGISTRY_PATH) as path:
        yield path


def load_template_spec(record: TemplateRegistryRecord) -> TemplateSpec:
    manifest = _bundled_pack_manifest(record.template_id)
    if manifest.is_file():
        return _load_template_pack(manifest, _BUNDLED_TEMPLATES.joinpath(record.template_id))
    path = _BUNDLED_TEMPLATES.joinpath(Path(record.bundle_path).name)
    if not path.is_file():
        raise FileNotFoundError(f"template bundle not found: {record.template_id}")
    return TemplateSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))

def bundled_template_source(record: TemplateRegistryRecord) -> tuple[str, str]:
    manifest = _bundled_pack_manifest(record.template_id)
    if manifest.is_file():
        return "bundled_pack", f"bundled_templates/{record.template_id}/template.v2.toml"
    return "bundled_json", record.bundle_path

def _bundled_pack_manifest(template_id: str) -> Any:
    return _BUNDLED_TEMPLATES.joinpath(template_id).joinpath("template.v2.toml")

def _load_template_pack(manifest: Any, pack_dir: Any) -> TemplateSpec:
    raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    files = []
    for declared in raw.get("files", []):
        source = declared.get("source")
        if not isinstance(source, str):
            raise ValueError("template pack files must declare source")
        files.append(
            {
                "path": declared.get("path"),
                "content": pack_dir.joinpath(source).read_text(encoding="utf-8"),
            }
        )
    payload = {
        "schema_version": raw.get("schema_version"),
        "name": raw.get("template_id") or raw.get("name"),
        "version": raw.get("version", ""),
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "minimum_agent_harness_version": raw.get("minimum_agent_harness_version"),
        "maximum_agent_harness_version": raw.get("maximum_agent_harness_version"),
        "required_capabilities": raw.get("required_capabilities", []),
        "parameters": raw.get("parameters", {}),
        "generated_schema_versions": raw.get("generated_schema_versions", {}),
        "provider_requirements": raw.get("provider_requirements", {}),
        "policy_requirements": raw.get("policy_requirements", {}),
        "retrieval_assumptions": raw.get("retrieval_assumptions", {}),
        "eval_or_demo_metadata": raw.get("eval_or_demo_metadata", {}),
        "files": files,
    }
    return TemplateSpec.model_validate(payload)
