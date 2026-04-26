from __future__ import annotations

import json
from pathlib import Path

from agent_harness.runtimes.native import HarnessRuntime, approve_action
from tests.conftest import seed_project


def test_approve_action_completes_paused_run_and_updates_audit_artifacts(
    tmp_path: Path, monkeypatch
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
                "task_id": "approval-resume",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "runtime-resume-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:30:00Z")

    paused = HarnessRuntime(tmp_path).run_task(task_path)

    assert paused.status == "paused"
    action_id = paused.approvals[0]
    run_dir = tmp_path / ".agent-harness" / "runs" / "runtime-resume-run"

    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:31:00Z")
    approval = approve_action(
        tmp_path,
        "runtime-resume-run",
        action_id,
        "approve",
        actor="reviewer",
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    action = json.loads((run_dir / "actions" / f"{action_id}.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert approval.status == "approved"
    assert target.read_text(encoding="utf-8") == (
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    assert summary["status"] == "completed"
    assert summary["message"] == "run complete"
    assert summary["events_count"] == len(events)
    assert action["observation"]["status"] == "ok"
    assert any(event["type"] == "approval_decided" for event in events)
    assert any(
        event["type"] == "run_finished" and event["payload"]["status"] == "completed"
        for event in events
    )


def test_runtime_records_model_actions_as_run_evidence(tmp_path: Path, monkeypatch) -> None:
    seed_project(tmp_path)
    target = tmp_path / "fixture.py"
    target.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "model-events",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "model-events-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:40:00Z")

    HarnessRuntime(tmp_path).run_task(task_path)

    events = [
        json.loads(line)
        for line in (tmp_path / ".agent-harness" / "runs" / "model-events-run" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    model_actions = [
        event["payload"]["call"] for event in events if event["type"] == "model_action"
    ]

    assert [call["tool_name"] for call in model_actions] == [
        "read_file",
        "search_code",
        "patch_file",
    ]


def test_denied_approval_leaves_file_unchanged_and_updates_run_summary(
    tmp_path: Path, monkeypatch
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
                "task_id": "denied-approval",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "denied-approval-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:50:00Z")

    paused = HarnessRuntime(tmp_path).run_task(task_path)

    assert paused.status == "paused"
    action_id = paused.approvals[0]
    run_dir = tmp_path / ".agent-harness" / "runs" / "denied-approval-run"

    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:51:00Z")
    approval = approve_action(
        tmp_path,
        "denied-approval-run",
        action_id,
        "deny",
        actor="reviewer",
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert approval.status == "denied"
    assert target.read_text(encoding="utf-8") == original
    assert summary["status"] == "failed"
    assert summary["events_count"] == len(events)
    assert any(event["type"] == "approval_decided" for event in events)
    assert any(
        event["type"] == "run_finished" and event["payload"]["status"] == "failed"
        for event in events
    )
