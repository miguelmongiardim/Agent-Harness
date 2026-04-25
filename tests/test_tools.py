from __future__ import annotations

from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import ApprovalRecord, PolicyProfile, TaskSpec, ToolCall
from agent_harness.tools import ToolExecutor
from agent_harness.utils import sha256_text


def test_patch_file_requires_bound_approval(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    original = "def add_numbers(a, b):\n    return a + b\n"
    target.write_text(original, encoding="utf-8")
    profile = PolicyProfile.model_validate(DEFAULT_POLICY)
    engine = PolicyEngine(tmp_path, profile)
    executor = ToolExecutor(tmp_path, engine)
    task = TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": "task",
            "title": "Task",
            "intent": "Refactor code",
            "target_paths": ["sample.py"],
        }
    )
    call = ToolCall(
        action_id="patch-1",
        tool_name="patch_file",
        arguments={
            "path": "sample.py",
            "before_hash": sha256_text(target.read_text(encoding="utf-8")),
            "proposed_content": "def add(a: int, b: int) -> int:\n    return a + b\n",
        },
        reason="patch",
    )

    pending, _ = executor.execute(call, task, "checkpoint")
    assert pending.status == "pending_approval"
    assert target.read_text(encoding="utf-8") == original

    approval = ApprovalRecord(
        approval_id="approval-1",
        run_id="run-1",
        action_id=call.action_id,
        tool_name=call.tool_name,
        arguments_hash=call.arguments_hash(),
        policy_profile=profile.name,
        checkpoint_hash="checkpoint",
        proposed_effect_hash=executor.proposed_effect_hash(call),
        status="approved",
        actor="test",
    )
    applied, _ = executor.execute(call, task, "checkpoint", approval=approval)

    assert applied.success
    assert "def add(a: int, b: int) -> int" in target.read_text(encoding="utf-8")
