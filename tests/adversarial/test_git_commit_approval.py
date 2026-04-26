from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_harness.runtimes.native import HarnessRuntime, approve_action
from agent_harness.utils import hash_file, sha256_text
from tests.conftest import seed_project


def test_git_commit_requires_separate_approval_and_commits_exact_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, run_id = _approved_patch_run(tmp_path, monkeypatch, "run-git-commit")
    parent_head = _git(tmp_path, "rev-parse", "HEAD")
    message = "refactor fixture addition"

    summary = HarnessRuntime(tmp_path).propose_git_commit(run_id, message)

    assert summary.status == "paused"
    commit_action_id = summary.approvals[-1]
    assert _git(tmp_path, "rev-parse", "HEAD") == parent_head

    run_dir = tmp_path / ".agent-harness" / "runs" / run_id
    approval = json.loads(
        (run_dir / "approvals" / f"{commit_action_id}.json").read_text(encoding="utf-8")
    )
    planned = json.loads((run_dir / "git_commit.json").read_text(encoding="utf-8"))

    assert approval["tool_name"] == "git_commit"
    assert approval["status"] == "pending"
    assert planned["parent_head"] == parent_head
    assert planned["file_set"] == ["fixture.py"]
    assert planned["content_hashes"] == {"fixture.py": hash_file(target)}
    assert planned["final_message_hash"] == sha256_text(message)

    approve_action(tmp_path, run_id, commit_action_id, "approve", actor="reviewer")

    assert _git(tmp_path, "rev-parse", "HEAD") != parent_head
    assert _git(tmp_path, "log", "-1", "--pretty=%B") == message
    assert _git(tmp_path, "show", "--name-only", "--pretty=", "HEAD").splitlines() == ["fixture.py"]


def test_git_commit_denies_message_drift_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _target, run_id = _approved_patch_run(tmp_path, monkeypatch, "run-git-message-drift")
    parent_head = _git(tmp_path, "rev-parse", "HEAD")
    summary = HarnessRuntime(tmp_path).propose_git_commit(run_id, "approved message")
    commit_action_id = summary.approvals[-1]

    plan_path = tmp_path / ".agent-harness" / "runs" / run_id / "git_commit.json"
    planned = json.loads(plan_path.read_text(encoding="utf-8"))
    planned["final_message"] = "tampered message"
    plan_path.write_text(json.dumps(planned, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="git commit approval binding"):
        approve_action(tmp_path, run_id, commit_action_id, "approve", actor="reviewer")

    assert _git(tmp_path, "rev-parse", "HEAD") == parent_head


def test_git_commit_denies_parent_head_drift_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _target, run_id = _approved_patch_run(tmp_path, monkeypatch, "run-git-parent-drift")
    summary = HarnessRuntime(tmp_path).propose_git_commit(run_id, "approved message")
    commit_action_id = summary.approvals[-1]

    _git(tmp_path, "commit", "--allow-empty", "-m", "parent drift")

    with pytest.raises(ValueError, match="parent HEAD changed"):
        approve_action(tmp_path, run_id, commit_action_id, "approve", actor="reviewer")

    assert _git(tmp_path, "log", "-1", "--pretty=%B") == "parent drift"


def test_git_commit_denies_pre_staged_unapproved_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _target, run_id = _approved_patch_run(tmp_path, monkeypatch, "run-git-staged-drift")
    parent_head = _git(tmp_path, "rev-parse", "HEAD")
    summary = HarnessRuntime(tmp_path).propose_git_commit(run_id, "approved message")
    commit_action_id = summary.approvals[-1]

    (tmp_path / "unapproved.py").write_text("print('unapproved')\n", encoding="utf-8")
    _git(tmp_path, "add", "unapproved.py")

    with pytest.raises(ValueError, match="staged changes"):
        approve_action(tmp_path, run_id, commit_action_id, "approve", actor="reviewer")

    assert _git(tmp_path, "rev-parse", "HEAD") == parent_head


def test_git_commit_respects_task_tool_narrowing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _target, run_id = _approved_patch_run(
        tmp_path,
        monkeypatch,
        "run-git-task-narrowing",
        allow_git_commit=False,
    )
    parent_head = _git(tmp_path, "rev-parse", "HEAD")

    with pytest.raises(PermissionError, match="tool not allowed by effective policy"):
        HarnessRuntime(tmp_path).propose_git_commit(run_id, "approved message")

    assert _git(tmp_path, "rev-parse", "HEAD") == parent_head


def _approved_patch_run(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_id: str,
    allow_git_commit: bool = True,
) -> tuple[Path, str]:
    seed_project(root)
    target = root / "fixture.py"
    target.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")
    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": run_id,
                "title": "Refactor",
                "intent": "Refactor add_numbers",
                "target_paths": ["fixture.py"],
                "allowed_tools": ["read_file", "patch_file"]
                + (["git_commit"] if allow_git_commit else []),
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    _init_git_repo(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", run_id)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T20:00:00Z")

    summary = HarnessRuntime(root).run_task(task_path)
    assert summary.status == "paused"
    patch_action_id = summary.approvals[0]

    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T20:01:00Z")
    approve_action(root, run_id, patch_action_id, "approve", actor="reviewer")

    assert "def add(a: int, b: int) -> int:" in target.read_text(encoding="utf-8")
    assert _git(root, "rev-parse", "HEAD")
    return target, run_id


def _init_git_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "agent-harness@example.test")
    _git(root, "config", "user.name", "Agent Harness Test")
    _git(root, "add", "agent-harness.yaml", "policies/default.json", "fixture.py", "task.json")
    _git(root, "commit", "-m", "initial")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip()
