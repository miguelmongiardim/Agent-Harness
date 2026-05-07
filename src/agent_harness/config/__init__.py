from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_harness.config.schema import HarnessConfig
from agent_harness.utils import write_json

T = TypeVar("T", bound=BaseModel)

DEFAULT_CONFIG = HarnessConfig(
    schema_version="config.v2",
    project_name="agent-harness",
    artifact_root=".agent-harness",
    default_policy="default",
    retrieval_backend="lexical",
    template_catalog="bundled",
)

EFFECTIVE_PUBLIC_SCHEMA_VERSIONS = {
    "config.v1": "config.v2",
    "config.v2": "config.v2",
    "task.v1": "task.v2",
    "task.v2": "task.v2",
    "policy.v1": "policy.v2",
    "policy.v2": "policy.v2",
}


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("["):
        return json.loads(value.replace("'", '"'))
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    records: list[tuple[int, str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        records.append((len(line) - len(line.lstrip(" ")), line.lstrip(" "), raw_line))

    data: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, data)]
    for index, (indent, line, raw_line) in enumerate(records):
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if line.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"unsupported config list item: {raw_line}")
            parent.append(_parse_scalar(line[2:]))
            continue
        if ":" not in line:
            raise ValueError(f"unsupported config line: {raw_line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"unsupported config mapping entry: {raw_line}")
        if raw_value.strip():
            parent[key] = _parse_scalar(raw_value)
        else:
            child: dict[str, Any] | list[Any] = (
                [] if _next_yaml_child_is_list(records, index, indent) else {}
            )
            parent[key] = child
            stack.append((indent, child))
    return data


def _next_yaml_child_is_list(
    records: list[tuple[int, str, str]],
    index: int,
    indent: int,
) -> bool:
    if index + 1 >= len(records):
        return False
    next_indent, next_line, _ = records[index + 1]
    return next_indent > indent and next_line.startswith("- ")


def load_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    loaded = json.loads(text) if text.lstrip().startswith("{") else parse_simple_yaml(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain an object")
    return loaded


def load_config(root: Path) -> HarnessConfig:
    path = root / "agent-harness.yaml"
    if not path.exists():
        return DEFAULT_CONFIG
    return _normalize_public_schema(HarnessConfig.model_validate(load_mapping(path)))


def load_config_with_schema_evidence(root: Path) -> tuple[HarnessConfig, dict[str, str]]:
    path = root / "agent-harness.yaml"
    if not path.exists():
        return DEFAULT_CONFIG, _schema_evidence(DEFAULT_CONFIG.schema_version)
    config = load_config(root)
    return config, _schema_evidence(_read_schema_version(path))


def write_default_config(root: Path, force: bool = False) -> Path:
    path = root / "agent-harness.yaml"
    if path.exists() and not force:
        return path
    text = "\n".join(
        [
            "schema_version: config.v2",
            f"project_name: {DEFAULT_CONFIG.project_name}",
            f"artifact_root: {DEFAULT_CONFIG.artifact_root}",
            f"default_policy: {DEFAULT_CONFIG.default_policy}",
            f"retrieval_backend: {DEFAULT_CONFIG.retrieval_backend}",
            f"template_catalog: {DEFAULT_CONFIG.template_catalog}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    return path


def load_model(path: Path, model_type: type[T]) -> T:
    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def load_public_model(path: Path, model_type: type[T]) -> T:
    return _normalize_public_schema(model_type.model_validate(load_mapping(path)))


def load_public_model_with_schema_evidence(
    path: Path, model_type: type[T]
) -> tuple[T, dict[str, str]]:
    model = load_public_model(path, model_type)
    return model, _schema_evidence(_read_schema_version(path))


def dump_model(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))


def _normalize_public_schema(model: T) -> T:
    schema_version = getattr(model, "schema_version", None)
    if not isinstance(schema_version, str):
        return model
    effective = EFFECTIVE_PUBLIC_SCHEMA_VERSIONS.get(schema_version, schema_version)
    if effective == schema_version:
        return model
    return model.model_copy(update={"schema_version": effective})


def _read_schema_version(path: Path) -> str:
    raw = load_mapping(path).get("schema_version")
    if not isinstance(raw, str):
        raise ValueError(f"{path} does not record a schema_version")
    return raw


def _schema_evidence(original: str) -> dict[str, str]:
    return {
        "original": original,
        "effective": EFFECTIVE_PUBLIC_SCHEMA_VERSIONS.get(original, original),
    }
