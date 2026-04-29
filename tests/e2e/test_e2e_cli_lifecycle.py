from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from tests.conftest import seed_project

pytestmark = [pytest.mark.slow, pytest.mark.golden_path]


def test_cli_run_approve_inspect_and_export_completes_full_lifecycle(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-e2e-lifecycle")

    seed_project(tmp_path)
    target = tmp_path / "fixtures" / "legacy_math.py"
    target.parent.mkdir(parents=True)
    target.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "e2e-lifecycle",
                "title": "Refactor lifecycle",
                "intent": "Refactor the helper while preserving behavior.",
                "target_paths": ["fixtures/legacy_math.py"],
                "allowed_tools": ["read_file", "patch_file"],
                "max_steps": 4,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(task_path)]) == 0
    assert main(["run", str(task_path)]) == 0

    summary = json.loads(
        (tmp_path / ".agent-harness" / "runs" / "run-e2e-lifecycle" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["status"] == "paused"
    action_id = summary["approvals"][0]

    assert main(["approve", "run-e2e-lifecycle", action_id, "--decision", "approve"]) == 0
    assert main(["inspect", "run", "run-e2e-lifecycle"]) == 0
    assert main(["export", "json", "run-e2e-lifecycle"]) == 0

    updated = target.read_text(encoding="utf-8")
    assert "def add(a: int, b: int) -> int:" in updated

    exported = json.loads(
        (tmp_path / ".agent-harness" / "exports" / "run-e2e-lifecycle.json").read_text(
            encoding="utf-8"
        )
    )
    assert exported["summary"]["status"] == "completed"
    assert any(event["type"] == "approval_decided" for event in exported["events"])
