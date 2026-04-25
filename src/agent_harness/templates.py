from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import TemplateSpec, ToolCall
from agent_harness.utils import stable_id


def list_templates() -> list[str]:
    root = resources.files("agent_harness").joinpath("bundled_templates")
    return sorted(path.name.removesuffix(".json") for path in root.iterdir() if path.name.endswith(".json"))


def load_template(name: str) -> TemplateSpec:
    root = resources.files("agent_harness").joinpath("bundled_templates")
    path = root.joinpath(f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"template not found: {name}")
    return TemplateSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))


def apply_template(
    spec: TemplateSpec,
    destination: Path,
    policy: PolicyEngine,
    force: bool = False,
) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for file in spec.files:
        call = ToolCall(
            action_id=stable_id("action", "template", spec.name, file.path),
            tool_name="patch_file",
            arguments={"path": file.path, "before_hash": "", "proposed_content": file.content},
            reason=f"apply template {spec.name}",
        )
        decision = policy.evaluate_tool_call(call, task=None, checkpoint_hash="template")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        target = destination / file.path
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    return written
