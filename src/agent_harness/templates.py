from __future__ import annotations

import difflib
import json
import sqlite3
from importlib import resources
from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    TemplateApplyRecord,
    TemplateDetail,
    TemplateProposedWrite,
    TemplateRegistryRecord,
    TemplateSpec,
    ToolCall,
)
from agent_harness.utils import sha256_text, stable_id

_BUNDLED_TEMPLATES = resources.files("agent_harness").joinpath("bundled_templates")
_REGISTRY_PATH = _BUNDLED_TEMPLATES.joinpath("registry.sqlite3")


def list_templates() -> list[TemplateRegistryRecord]:
    with resources.as_file(_REGISTRY_PATH) as registry_path, sqlite3.connect(registry_path) as conn:
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
    spec = _load_template_spec(record)
    return TemplateDetail(
        template_id=record.template_id,
        version=record.version,
        title=record.title,
        description=record.description,
        bundle_path=record.bundle_path,
        tags=record.tags,
        files=spec.files,
    )


def load_template_record(name: str) -> TemplateRegistryRecord:
    for record in list_templates():
        if record.template_id == name:
            return record
    raise FileNotFoundError(f"template not found: {name}")


def _load_template_spec(record: TemplateRegistryRecord) -> TemplateSpec:
    path = _BUNDLED_TEMPLATES.joinpath(Path(record.bundle_path).name)
    if not path.is_file():
        raise FileNotFoundError(f"template bundle not found: {record.template_id}")
    return TemplateSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))


def plan_template_apply(
    spec: TemplateDetail,
    destination: Path,
    policy: PolicyEngine,
    force: bool = False,
) -> TemplateApplyRecord:
    try:
        destination_path = destination.resolve().relative_to(policy.project_root).as_posix()
    except ValueError as exc:
        raise PermissionError("template destination outside project root") from exc

    writes: list[TemplateProposedWrite] = []
    for file in spec.files:
        target = destination / file.path
        try:
            policy_path = target.resolve().relative_to(policy.project_root).as_posix()
        except ValueError as exc:
            raise PermissionError("template destination outside project root") from exc
        call = ToolCall(
            action_id=stable_id("action", "template", spec.template_id, policy_path),
            tool_name="patch_file",
            arguments={
                "path": policy_path,
                "before_hash": "",
                "proposed_content": file.content,
            },
            reason=f"apply template {spec.template_id}",
        )
        decision = policy.evaluate_tool_call(call, task=None, checkpoint_hash="template_apply")
        if not decision.allowed:
            raise PermissionError(decision.reason)

        if target.exists():
            if not force:
                raise FileExistsError(
                    f"template apply would overwrite existing file: {policy_path}"
                )
            before = target.read_text(encoding="utf-8")
        else:
            before = ""
        writes.append(
            TemplateProposedWrite(
                path=policy_path,
                before_hash=sha256_text(before),
                after_hash=sha256_text(file.content),
                diff=_diff(before, file.content, policy_path),
                proposed_content=file.content,
            )
        )
    return TemplateApplyRecord(
        template_id=spec.template_id,
        version=spec.version,
        title=spec.title,
        description=spec.description,
        destination=destination_path,
        proposed_writes=writes,
        force=force,
    )


def _diff(before: str, after: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
