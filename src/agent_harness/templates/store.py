from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from agent_harness.schemas import TemplateRegistryRecord, TemplateSpec

_BUNDLED_TEMPLATES = resources.files("agent_harness").joinpath("bundled_templates")
_REGISTRY_PATH = _BUNDLED_TEMPLATES.joinpath("registry.sqlite3")


@contextmanager
def registry_path() -> Iterator[Path]:
    with resources.as_file(_REGISTRY_PATH) as path:
        yield path


def load_template_spec(record: TemplateRegistryRecord) -> TemplateSpec:
    path = _BUNDLED_TEMPLATES.joinpath(Path(record.bundle_path).name)
    if not path.is_file():
        raise FileNotFoundError(f"template bundle not found: {record.template_id}")
    return TemplateSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
