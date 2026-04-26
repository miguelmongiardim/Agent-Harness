from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import PolicyProfile
from tests.conftest import seed_project


def test_recursive_deny_globs_match_root_and_nested_paths_before_roots(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    assert not engine.evaluate_path("secret.py", "read", "context_source").allowed
    assert not engine.evaluate_path("config/secret.py", "read", "context_source").allowed
    assert not engine.evaluate_path("secret.py", "write", "tool:patch_file").allowed
    assert not engine.evaluate_path("config/secret.py", "write", "tool:patch_file").allowed


def test_denied_target_file_is_excluded_from_context_and_denied_by_tool_policy(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    allowed = tmp_path / "src" / "allowed.py"
    denied = tmp_path / "config" / "secret.py"
    allowed.parent.mkdir()
    denied.parent.mkdir()
    allowed.write_text("def visible() -> str:\n    return 'allowed'\n", encoding="utf-8")
    denied.write_text("API_KEY = 'should-not-enter-context'\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "denied-data",
                "title": "Inspect allowed and denied data",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["src/allowed.py", "config/secret.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-denied-data"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    manifest = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-denied-data"
            / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert [source["path"] for source in manifest["sources"]] == ["src/allowed.py"]
    assert "allowed" in json.dumps(manifest)
    assert "should-not-enter-context" not in json.dumps(manifest)

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-denied-data"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    context_decisions = [
        event["payload"]["decision"]
        for event in inspected["events"]
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "context_source"
    ]
    assert {decision["allowed"] for decision in context_decisions} == {False, True}

    denied_observations = [
        event["payload"]["observation"]
        for event in inspected["events"]
        if event["type"] == "tool_observation"
        and event["payload"]["observation"]["status"] == "denied"
    ]
    assert len(denied_observations) == 1
    assert denied_observations[0]["tool_name"] == "read_file"
    assert denied_observations[0]["error"].startswith("path denied by glob")


def test_search_observations_redact_secret_like_content_before_storage(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    target = tmp_path / "src" / "config.py"
    target.parent.mkdir()
    target.write_text("API_KEY = 'visible-to-search'\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "redact-search",
                "title": "Search for a token",
                "intent": "Search code without changing files.",
                "target_paths": [],
                "context_queries": ["API_KEY"],
                "allowed_tools": ["search_code"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-redact-search"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-redact-search"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    search_observations = [
        event["payload"]["observation"]
        for event in inspected["events"]
        if event["type"] == "tool_observation"
        and event["payload"]["observation"]["tool_name"] == "search_code"
    ]
    assert len(search_observations) == 1
    stored_observation = json.dumps(search_observations[0])
    assert "[REDACTED]" in stored_observation
    assert "visible-to-search" not in stored_observation


def test_context_and_read_observations_redact_secret_like_content_before_storage(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    target = tmp_path / "src" / "settings.py"
    target.parent.mkdir()
    target.write_text("password = 'visible-to-read'\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "redact-read",
                "title": "Read a file containing a secret-like value",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["src/settings.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-redact-read"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    manifest_text = (
        tmp_path
        / ".agent-harness"
        / "runs"
        / "run-redact-read"
        / "context_manifest.json"
    ).read_text(encoding="utf-8")
    assert "[REDACTED]" in manifest_text
    assert "visible-to-read" not in manifest_text

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-redact-read"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    read_observations = [
        event["payload"]["observation"]
        for event in inspected["events"]
        if event["type"] == "tool_observation"
        and event["payload"]["observation"]["tool_name"] == "read_file"
    ]
    assert len(read_observations) == 1
    stored_observation = json.dumps(read_observations[0])
    assert "[REDACTED]" in stored_observation
    assert "visible-to-read" not in stored_observation


def test_task_allowed_tools_cannot_widen_policy_profile_tool_ceiling(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    target = tmp_path / "src" / "sample.py"
    target.parent.mkdir()
    target.write_text("def visible() -> str:\n    return 'needle'\n", encoding="utf-8")
    read_only_policy = dict(DEFAULT_POLICY)
    read_only_policy["name"] = "read-only"
    read_only_policy["allowed_tools"] = ["read_file"]
    (tmp_path / "policies" / "read-only.json").write_text(
        json.dumps(read_only_policy, indent=2),
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "profile-ceiling",
                "title": "Try to widen allowed tools",
                "intent": "Inspect and search without changing files.",
                "policy_profile": "read-only",
                "target_paths": ["src/sample.py"],
                "context_queries": ["needle"],
                "allowed_tools": ["read_file", "search_code"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-profile-ceiling"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-profile-ceiling"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    observations = [
        event["payload"]["observation"]
        for event in inspected["events"]
        if event["type"] == "tool_observation"
    ]
    assert [observation["status"] for observation in observations] == ["ok", "denied"]
    assert observations[1]["tool_name"] == "search_code"
    assert observations[1]["error"] == "tool not allowed by effective policy"
    tool_decisions = [
        event["payload"]["decision"]
        for event in inspected["events"]
        if event["type"] == "policy_decision" and "action_id" in event["payload"]
    ]
    assert [decision["allowed"] for decision in tool_decisions] == [True, False]
