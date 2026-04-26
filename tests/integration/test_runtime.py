from __future__ import annotations

import json
from pathlib import Path

from agent_harness.runtimes.native import HarnessRuntime
from tests.conftest import seed_project


def test_runtime_dry_run_produces_approval_without_patching(tmp_path: Path, monkeypatch) -> None:
    seed_project(tmp_path)
    fixture = tmp_path / "fixture.py"
    original = "def add_numbers(a, b):\n    return a + b\n"
    fixture.write_text(original, encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "python-refactor-add",
                "title": "Refactor",
                "intent": "Refactor add_numbers",
                "target_paths": ["fixture.py"],
                "allowed_tools": ["read_file", "patch_file"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-fixed")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T12:00:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)

    assert summary.status == "dry_run"
    assert fixture.read_text(encoding="utf-8") == original
    assert (tmp_path / ".agent-harness" / "runs" / "run-fixed" / "context_manifest.json").exists()
    assert summary.approvals
