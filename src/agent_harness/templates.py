from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import TemplateSpec, ToolCall
from agent_harness.utils import stable_id


def list_templates() -> list[str]:
    root = resources.files("agent_harness").joinpath("bundled_templates")
    return sorted(
        path.name.removesuffix(".json")
        for path in root.iterdir()
        if path.name.endswith(".json")
    )


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
    written: list[Path] = []
    for file in spec.files:
        target = destination / file.path
        try:
            policy_path = target.resolve().relative_to(policy.project_root).as_posix()
        except ValueError as exc:
            raise PermissionError("template destination outside project root") from exc
        call = ToolCall(
            action_id=stable_id("action", "template", spec.name, policy_path),
            tool_name="patch_file",
            arguments={
                "path": policy_path,
                "before_hash": "",
                "proposed_content": file.content,
            },
            reason=f"apply template {spec.name}",
        )
        decision = policy.evaluate_tool_call(call, task=None, checkpoint_hash="template")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    return written
