from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.policy.schema import PolicyProfile
from agent_harness.runtimes.native import HarnessRuntime, approve_action
from agent_harness.tasks.schema import TaskSpec
from agent_harness.tools import ToolExecutor
from agent_harness.tools.schema import ToolCall
from tests.conftest import seed_project


def test_runtime_records_pending_patch_approval_and_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    target = tmp_path / "fixture.py"
    original = "def add_numbers(a, b):\n    return a + b\n"
    target.write_text(original, encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "patch-approval",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-patch-approval")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T13:00:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "paused"
    assert len(summary.approvals) == 1
    assert target.read_text(encoding="utf-8") == original

    run_dir = tmp_path / ".agent-harness" / "runs" / "run-patch-approval"
    action_id = summary.approvals[0]
    approval = json.loads((run_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8"))
    action = json.loads((run_dir / "actions" / f"{action_id}.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert approval["run_id"] == "run-patch-approval"
    assert approval["status"] == "pending"
    assert action["observation"]["status"] == "pending_approval"
    assert action["observation"]["output"]["path"] == "fixture.py"
    assert "--- a/fixture.py" in action["observation"]["output"]["diff"]
    assert "+++ b/fixture.py" in action["observation"]["output"]["diff"]
    assert any(event["type"] == "approval_recorded" for event in events)
    assert any(
        event["type"] == "tool_observation"
        and event["payload"]["observation"]["status"] == "pending_approval"
        for event in events
    )


def test_approve_action_rejects_tampered_action_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    target = tmp_path / "fixture.py"
    original = "def add_numbers(a, b):\n    return a + b\n"
    target.write_text(original, encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "tampered-approval",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-tampered-approval")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T13:15:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)
    assert summary.status == "paused"

    run_dir = tmp_path / ".agent-harness" / "runs" / "run-tampered-approval"
    action_id = summary.approvals[0]
    action_path = run_dir / "actions" / f"{action_id}.json"
    action = json.loads(action_path.read_text(encoding="utf-8"))
    action["call"]["arguments"]["proposed_content"] = "tampered\n"
    action_path.write_text(json.dumps(action, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="approval binding does not match action"):
        approve_action(tmp_path, "run-tampered-approval", action_id, "approve", actor="reviewer")

    assert target.read_text(encoding="utf-8") == original


def test_run_tests_denies_non_allow_listed_command(tmp_path: Path) -> None:
    seed_project(tmp_path)
    profile = PolicyProfile.model_validate(DEFAULT_POLICY)
    executor = ToolExecutor(
        tmp_path,
        policy=PolicyEngine(tmp_path, profile),
    )
    task = TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": "task",
            "title": "Task",
            "intent": "Run tests",
            "allowed_tools": ["run_tests"],
            "test_commands": [["python", "-m", "pytest"]],
        }
    )
    call = ToolCall(
        action_id="run-tests-1",
        tool_name="run_tests",
        arguments={"command": ["python", "-m", "pytest", "tests", "-k", "tool_approval"]},
        reason="run targeted tests",
    )

    observation, decision = executor.execute(call, task, "checkpoint", run_id="run-1")

    assert not observation.success
    assert observation.status == "denied"
    assert decision.reason == "test command not allowed by policy"
