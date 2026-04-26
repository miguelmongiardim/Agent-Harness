from __future__ import annotations

import subprocess
from pathlib import Path

from agent_harness.schemas import ToolCall, ToolObservation


def execute_git_status(call: ToolCall, project_root: Path) -> ToolObservation:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return ToolObservation(
        action_id=call.action_id,
        tool_name=call.tool_name,
        success=completed.returncode == 0,
        status="ok" if completed.returncode == 0 else "failed",
        output={
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )
