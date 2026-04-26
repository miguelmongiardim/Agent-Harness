from __future__ import annotations

import subprocess
from pathlib import Path

from agent_harness.schemas import ToolCall, ToolObservation
from agent_harness.tools.registry import ToolArgs
from agent_harness.utils import truncate


class RunTestsArgs(ToolArgs):
    command: list[str]


def execute_run_tests(
    call: ToolCall,
    args: RunTestsArgs,
    project_root: Path,
) -> ToolObservation:
    completed = subprocess.run(
        args.command,
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return ToolObservation(
        action_id=call.action_id,
        tool_name=call.tool_name,
        success=completed.returncode == 0,
        status="ok" if completed.returncode == 0 else "failed",
        output={
            "command": args.command,
            "returncode": completed.returncode,
            "stdout": truncate(completed.stdout),
            "stderr": truncate(completed.stderr),
        },
    )
