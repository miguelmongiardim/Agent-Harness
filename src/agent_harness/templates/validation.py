from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from agent_harness.config import write_default_config
from agent_harness.core.runtime import HarnessRuntime
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.release import RELEASE_EVIDENCE_DIR
from agent_harness.templates.registry import list_templates, load_template
from agent_harness.utils import now_utc, write_json


def validate_templates(
    project_root: Path,
    *,
    template_id: str | None = None,
    all_templates: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    if all_templates == (template_id is not None):
        raise ValueError("use either --all or a template id")

    listed = {record.template_id: record for record in list_templates()}
    selected_ids = sorted(listed) if all_templates else [str(template_id)]
    work_root = project_root / ".agent-harness" / "template-validation" / "work"
    results = [
        _validate_template(project_root, work_root, selected_id, selected_id in listed)
        for selected_id in selected_ids
    ]
    report = {
        "schema_version": "template_validation.v1",
        "status": "passed" if all(result["status"] == "passed" for result in results) else "failed",
        "generated_at": now_utc().isoformat(),
        "templates": results,
    }
    if output is not None:
        write_json(output, report)
    if all_templates:
        write_json(project_root / RELEASE_EVIDENCE_DIR / "template-validation.json", report)
    return report


def _validate_template(
    project_root: Path,
    work_root: Path,
    template_id: str,
    listed: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "template_id": template_id,
        "listed": listed,
        "shown": False,
        "status": "failed",
        "apply": {},
    }
    if not listed:
        result["message"] = "template is not listed in the bundled registry"
        return result

    try:
        detail = load_template(template_id)
        result["shown"] = detail.template_id == template_id and bool(detail.files)
        sandbox = work_root / template_id
        _reset_validation_sandbox(project_root, sandbox)
        destination = sandbox / "scaffold"
        summary = HarnessRuntime(sandbox).apply_template(template_id, destination)
        result["apply"] = {
            "run_id": summary.run_id,
            "status": summary.status,
            "approvals": summary.approvals,
            "destination": _project_relative(project_root, destination),
            "artifacts": _rebase_artifacts(project_root, sandbox, summary.artifacts),
        }
        result["status"] = (
            "passed"
            if result["shown"]
            and summary.status == "completed"
            and not summary.approvals
            and all((destination / file.path).exists() for file in detail.files)
            else "failed"
        )
        result["message"] = "passed" if result["status"] == "passed" else "validation failed"
    except Exception as exc:  # pragma: no cover - surfaced as validation data
        result["message"] = str(exc)
    return result


def _reset_validation_sandbox(project_root: Path, sandbox: Path) -> None:
    resolved_root = (project_root / ".agent-harness" / "template-validation").resolve()
    resolved_sandbox = sandbox.resolve()
    try:
        resolved_sandbox.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("template validation sandbox must stay under .agent-harness") from exc
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)
    write_default_config(sandbox, force=True)
    write_json(sandbox / "policies" / "default.json", DEFAULT_POLICY)


def _rebase_artifacts(
    project_root: Path,
    sandbox: Path,
    artifacts: dict[str, str],
) -> dict[str, str]:
    return {
        name: _project_relative(project_root, sandbox / relative)
        for name, relative in artifacts.items()
    }


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
