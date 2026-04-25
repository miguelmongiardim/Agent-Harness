from __future__ import annotations

from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import PolicyProfile, TaskSpec, ToolCall


def test_task_can_only_narrow_policy_tools(tmp_path: Path) -> None:
    profile = PolicyProfile.model_validate(DEFAULT_POLICY)
    task = TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": "task",
            "title": "Task",
            "intent": "Refactor code",
            "target_paths": ["src/example.py"],
            "allowed_tools": ["patch_file"],
        }
    )
    engine = PolicyEngine(tmp_path, profile)
    read = ToolCall(
        action_id="a1",
        tool_name="read_file",
        arguments={"path": "src/example.py"},
        reason="read",
    )
    patch = ToolCall(
        action_id="a2",
        tool_name="patch_file",
        arguments={"path": "src/example.py", "before_hash": "", "proposed_content": ""},
        reason="patch",
    )

    assert not engine.evaluate_tool_call(read, task, "checkpoint").allowed
    patch_decision = engine.evaluate_tool_call(patch, task, "checkpoint")
    assert patch_decision.allowed
    assert patch_decision.approval_required


def test_policy_denies_traversal_and_denied_globs(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    assert not engine.evaluate_path("../secret.py", "read", "test").allowed
    assert not engine.evaluate_path(".git/config", "read", "test").allowed


def test_policy_sensitivity_defaults(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    assert engine.classify_path("src/public.py") == "public"
    assert engine.classify_path("config/.env") == "secret"
