from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from agent_harness.schemas import HarnessConfig
from agent_harness.utils import write_json

T = TypeVar("T", bound=BaseModel)


DEFAULT_CONFIG = HarnessConfig(
    schema_version="config.v1",
    project_name="agent-harness",
    artifact_root=".agent-harness",
    default_policy="default",
    retrieval_backend="lexical",
    template_catalog="bundled",
)


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
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(_parse_scalar(line[4:]))
            continue
        if ":" not in line:
            raise ValueError(f"unsupported config line: {raw_line}")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if raw_value.strip():
            data[key] = _parse_scalar(raw_value)
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


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
    return HarnessConfig.model_validate(load_mapping(path))


def write_default_config(root: Path, force: bool = False) -> Path:
    path = root / "agent-harness.yaml"
    if path.exists() and not force:
        return path
    text = "\n".join(
        [
            "schema_version: config.v1",
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


def dump_model(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))
