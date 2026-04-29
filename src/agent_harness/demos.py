from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agent_harness.core.runtime import HarnessRuntime
from agent_harness.release import RELEASE_EVIDENCE_DIR
from agent_harness.storage.schema import RunSummary
from agent_harness.utils import now_utc, write_json

PROVIDER_AUDIT_DEMO_ID = "provider-audit"
PROVIDER_AUDIT_COMMAND = "agent-harness demo provider-audit"
PROVIDER_AUDIT_WORKSPACE = Path("examples") / "provider_audit"
PROVIDER_AUDIT_ENDPOINT_ENV = "AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT"
PROVIDER_AUDIT_API_KEY_ENV = "AGENT_HARNESS_PROVIDER_AUDIT_API_KEY"
RECORDED_PROVIDER_AUDIT_ENDPOINT = "recorded://openai_compatible/read_only"
RECORDED_PROVIDER_AUDIT_API_KEY = "recorded-provider-audit"
PYTHON_REFACTOR_DEMO_ID = "python-refactor"
PYTHON_REFACTOR_TASK = Path("examples") / "tasks" / "python_refactor.json"
PYTHON_REFACTOR_COMMAND = "agent-harness run examples/tasks/python_refactor.json --dry-run"


def run_provider_audit_demo(project_root: Path) -> dict[str, Any]:
    workspace = project_root / PROVIDER_AUDIT_WORKSPACE
    task_path = workspace / "task.json"
    if not task_path.exists():
        raise FileNotFoundError("provider-audit demo requires examples/provider_audit/task.json")

    with (
        _default_env(PROVIDER_AUDIT_ENDPOINT_ENV, RECORDED_PROVIDER_AUDIT_ENDPOINT),
        _default_env(PROVIDER_AUDIT_API_KEY_ENV, RECORDED_PROVIDER_AUDIT_API_KEY),
    ):
        summary = HarnessRuntime(workspace).run_task(task_path, auto_approve=True)

    artifacts = _rebase_artifacts(project_root, workspace, summary.artifacts)
    inspect = {
        "cwd": PROVIDER_AUDIT_WORKSPACE.as_posix(),
        "command": f"agent-harness inspect run {summary.run_id}",
    }
    payload = {
        "schema_version": "demo_run.v1",
        "demo_id": PROVIDER_AUDIT_DEMO_ID,
        "command": PROVIDER_AUDIT_COMMAND,
        "workspace": PROVIDER_AUDIT_WORKSPACE.as_posix(),
        "run_id": summary.run_id,
        "status": summary.status,
        "summary": summary.model_dump(mode="json"),
        "inspect": inspect,
        "artifacts": artifacts,
    }
    _write_demo_evidence(project_root, payload)
    return payload


def _write_demo_evidence(project_root: Path, payload: dict[str, Any]) -> None:
    evidence = {
        "schema_version": "release_demo_evidence.v1",
        "status": "passed" if payload["status"] == "completed" else "failed",
        "generated_at": now_utc().isoformat(),
        "demo_id": payload["demo_id"],
        "command": payload["command"],
        "workspace": payload["workspace"],
        "run_id": payload["run_id"],
        "summary_status": payload["status"],
        "inspect": payload["inspect"],
        "artifacts": payload["artifacts"],
    }
    write_json(
        project_root / RELEASE_EVIDENCE_DIR / "demo-provider-audit.json",
        evidence,
    )


def record_python_refactor_demo_if_applicable(
    project_root: Path,
    task_path: Path,
    summary: RunSummary,
    *,
    dry_run: bool,
) -> None:
    if not dry_run or not _same_path(project_root, task_path, PYTHON_REFACTOR_TASK):
        return
    artifacts = _rebase_artifacts(project_root, project_root, summary.artifacts)
    evidence = {
        "schema_version": "release_demo_evidence.v1",
        "status": "passed" if summary.status == "dry_run" else "failed",
        "generated_at": now_utc().isoformat(),
        "demo_id": PYTHON_REFACTOR_DEMO_ID,
        "command": PYTHON_REFACTOR_COMMAND,
        "workspace": ".",
        "task_path": PYTHON_REFACTOR_TASK.as_posix(),
        "run_id": summary.run_id,
        "summary_status": summary.status,
        "inspect": {
            "cwd": ".",
            "command": f"agent-harness inspect run {summary.run_id}",
        },
        "artifacts": artifacts,
    }
    write_json(
        project_root / RELEASE_EVIDENCE_DIR / "demo-python-refactor.json",
        evidence,
    )


def _rebase_artifacts(
    project_root: Path,
    workspace: Path,
    artifacts: dict[str, str],
) -> dict[str, str]:
    return {
        name: _project_relative(project_root, workspace / relative)
        for name, relative in artifacts.items()
    }


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _same_path(project_root: Path, candidate: Path, expected_relative: Path) -> bool:
    candidate_path = candidate if candidate.is_absolute() else project_root / candidate
    return candidate_path.resolve() == (project_root / expected_relative).resolve()


@contextmanager
def _default_env(name: str, value: str) -> Iterator[None]:
    previous = os.environ.get(name)
    if previous is None:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous
