from __future__ import annotations

import difflib

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import ToolCall, ToolObservation
from agent_harness.tools.registry import ToolArgs
from agent_harness.utils import sha256_text


class PatchFileArgs(ToolArgs):
    path: str
    before_hash: str
    proposed_content: str


def execute_patch_file(
    call: ToolCall,
    args: PatchFileArgs,
    policy: PolicyEngine,
) -> ToolObservation:
    path = policy.resolve_relative(args.path)
    if not path.exists():
        current_hash = ""
        current_content = ""
    else:
        current_content = path.read_text(encoding="utf-8")
        current_hash = sha256_text(current_content)
    if current_hash != args.before_hash:
        return ToolObservation(
            action_id=call.action_id,
            tool_name=call.tool_name,
            success=False,
            status="failed",
            error="before_hash did not match current file content",
            output={"expected": args.before_hash, "actual": current_hash},
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args.proposed_content, encoding="utf-8")
    return ToolObservation(
        action_id=call.action_id,
        tool_name=call.tool_name,
        success=True,
        status="ok",
        output={
            "path": args.path,
            "before_hash": current_hash,
            "after_hash": sha256_text(path.read_text(encoding="utf-8")),
            "diff": unified_diff(current_content, args.proposed_content, args.path),
        },
    )


def proposed_patch_effect_hash(args: PatchFileArgs, policy: PolicyEngine) -> str:
    return sha256_text(diff_for_patch(args, policy) + "\n" + args.proposed_content)


def diff_for_patch(args: PatchFileArgs, policy: PolicyEngine) -> str:
    path = policy.resolve_relative(args.path)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    return unified_diff(current, args.proposed_content, args.path)


def unified_diff(before: str, after: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
