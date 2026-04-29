from __future__ import annotations

from agent_harness.policy import PolicyEngine
from agent_harness.tools.registry import ToolArgs
from agent_harness.tools.schema import ToolCall, ToolObservation
from agent_harness.utils import sha256_text


class ReadFileArgs(ToolArgs):
    path: str


def execute_read_file(
    call: ToolCall,
    args: ReadFileArgs,
    policy: PolicyEngine,
) -> ToolObservation:
    path = policy.resolve_relative(args.path)
    content = path.read_text(encoding="utf-8")
    redacted, redactions = policy.redact_text(content)
    return ToolObservation(
        action_id=call.action_id,
        tool_name=call.tool_name,
        success=True,
        status="ok",
        output={
            "path": args.path,
            "content": redacted,
            "content_hash": sha256_text(content),
            "redactions": redactions,
        },
    )
