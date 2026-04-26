from __future__ import annotations

from agent_harness.schemas import PolicyProfile, TaskSpec


def test_command_allowed(
    command: list[str],
    profile: PolicyProfile,
    task: TaskSpec | None,
) -> bool:
    if command not in profile.allowed_test_commands:
        return False
    return task is None or not task.test_commands or command in task.test_commands
