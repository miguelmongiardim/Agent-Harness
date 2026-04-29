from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from agent_harness.config import EFFECTIVE_PUBLIC_SCHEMA_VERSIONS, load_mapping
from agent_harness.config.schema import HarnessConfig
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy.schema import PolicyProfile
from agent_harness.tasks.schema import TaskSpec
from agent_harness.templates.schema import TemplateSpec
from agent_harness.utils import write_json

_EXCLUDED_DIRS = {
    ".agent-harness",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv-win",
    "__pycache__",
}

_MODEL_BY_KIND: dict[str, type[BaseModel]] = {
    "config": HarnessConfig,
    "policy": PolicyProfile,
    "task": TaskSpec,
    "template": TemplateSpec,
}


def migrate_schemas(
    root: Path, *, write: bool = False, output: Path | None = None
) -> dict[str, Any]:
    records = [_migration_record(root, path, write=write) for path in _discover_inputs(root)]
    report = {
        "schema_version": "schema_migration_report.v1",
        "mode": "write" if write else "report",
        "write_enabled": write,
        "status": "completed",
        "records": records,
        "summary": {
            "files_scanned": len(records),
            "files_with_changes": sum(bool(record["changed_fields"]) for record in records),
            "files_written": sum(bool(record["written"]) for record in records),
            "files_skipped": sum(bool(record["unsupported_upgrade_reasons"]) for record in records),
        },
    }
    if output is not None:
        target = output if output.is_absolute() else root / output
        try:
            report["artifact"] = target.relative_to(root).as_posix()
        except ValueError:
            report["artifact"] = str(target)
        write_json(target, report)
    return report


def _discover_inputs(root: Path) -> list[Path]:
    discovered: list[Path] = []
    config_path = root / "agent-harness.yaml"
    if config_path.exists():
        discovered.append(config_path)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == config_path:
            continue
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            continue
        try:
            schema_version = load_mapping(path).get("schema_version")
        except (OSError, ValueError):
            continue
        if isinstance(schema_version, str) and _schema_kind(schema_version) is not None:
            discovered.append(path)
    return discovered


def _migration_record(root: Path, path: Path, *, write: bool) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    raw = load_mapping(path)
    original = raw.get("schema_version")
    if not isinstance(original, str):
        raise ValueError(f"{relative} does not record a schema_version")
    kind = _schema_kind(original)
    if kind is None:
        raise ValueError(f"{relative} has unsupported schema_version: {original}")

    effective = _effective_schema_version(original)
    unsupported = _unsupported_upgrade_reasons(original)
    changed_fields = ["schema_version"] if effective != original and not unsupported else []
    warnings: list[str] = []
    if changed_fields and not write:
        warnings.append("report mode only; rerun with --write to apply safe schema updates")
    if unsupported:
        warnings.append("file left unchanged because no safe deterministic upgrade is available")

    validation_warning = _validation_warning(kind, raw)
    if validation_warning is not None:
        warnings.append(validation_warning)
    written = False
    if write and changed_fields and not unsupported and validation_warning is None:
        _write_upgraded_input(path, kind, raw, effective)
        written = True

    return {
        "path": relative,
        "input_kind": kind,
        "original_schema_version": original,
        "effective_schema_version": effective,
        "changed_fields": changed_fields,
        "unchanged_fields": sorted(key for key in raw if key not in changed_fields),
        "warnings": warnings,
        "unsupported_upgrade_reasons": unsupported,
        "written": written,
    }


def _schema_kind(schema_version: str) -> str | None:
    if schema_version.startswith("config."):
        return "config"
    if schema_version.startswith("policy."):
        return "policy"
    if schema_version.startswith("task."):
        return "task"
    if schema_version.startswith("template."):
        return "template"
    return None


def _effective_schema_version(schema_version: str) -> str:
    if schema_version == "template.v1":
        return "template.v1"
    return EFFECTIVE_PUBLIC_SCHEMA_VERSIONS.get(schema_version, schema_version)


def _unsupported_upgrade_reasons(schema_version: str) -> list[str]:
    if schema_version == "template.v1":
        return ["template.v2 migration waits for template compatibility metadata"]
    return []


def _validation_warning(kind: str, raw: dict[str, Any]) -> str | None:
    try:
        _MODEL_BY_KIND[kind].model_validate(raw)
    except ValidationError as exc:
        return f"input does not validate cleanly: {exc.errors()[0]['msg']}"
    return None


def _write_upgraded_input(
    path: Path, kind: str, raw: dict[str, Any], effective_schema_version: str
) -> None:
    if kind == "config":
        config = HarnessConfig.model_validate(raw).model_copy(
            update={"schema_version": effective_schema_version}
        )
        _write_config(path, config)
        return
    if kind == "policy":
        legacy = PolicyProfile.model_validate(raw)
        payload = legacy.model_dump(mode="json")
        payload["schema_version"] = effective_schema_version
        if payload.get("template_capabilities") is None:
            payload["template_capabilities"] = DEFAULT_POLICY["template_capabilities"]
        if payload.get("migration") is None:
            payload["migration"] = DEFAULT_POLICY["migration"]
        upgraded_policy = PolicyProfile.model_validate(payload)
        write_json(path, upgraded_policy.model_dump(mode="json"))
        return
    model_type = _MODEL_BY_KIND[kind]
    upgraded = model_type.model_validate({**raw, "schema_version": effective_schema_version})
    write_json(path, upgraded.model_dump(mode="json"))


def _write_config(path: Path, config: HarnessConfig) -> None:
    lines = [
        f"schema_version: {config.schema_version}",
        f"project_name: {config.project_name}",
        f"artifact_root: {config.artifact_root}",
        f"default_policy: {config.default_policy}",
        f"retrieval_backend: {config.retrieval_backend}",
        f"template_catalog: {config.template_catalog}",
    ]
    if config.default_provider_profile is not None:
        lines.append(f"default_provider_profile: {config.default_provider_profile}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
