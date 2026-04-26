from __future__ import annotations

from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ApprovalRecord,
    PolicyDecision,
    TaskSpec,
    ToolCall,
    ToolObservation,
)
from agent_harness.tools.git_status import execute_git_status
from agent_harness.tools.patch_file import (
    PatchFileArgs,
    diff_for_patch,
    execute_patch_file,
    proposed_patch_effect_hash,
)
from agent_harness.tools.read_file import ReadFileArgs, execute_read_file
from agent_harness.tools.run_tests import RunTestsArgs, execute_run_tests
from agent_harness.tools.search_code import SearchCodeArgs, execute_search_code
from agent_harness.utils import sha256_text


class ToolExecutor:
    def __init__(self, project_root: Path, policy: PolicyEngine) -> None:
        self.project_root = project_root.resolve()
        self.policy = policy

    def execute(
        self,
        call: ToolCall,
        task: TaskSpec | None,
        checkpoint_hash: str,
        run_id: str | None = None,
        approval: ApprovalRecord | None = None,
        dry_run: bool = False,
    ) -> tuple[ToolObservation, PolicyDecision]:
        decision = self.policy.evaluate_tool_call(call, task, checkpoint_hash)
        if not decision.allowed:
            return (
                ToolObservation(
                    action_id=call.action_id,
                    tool_name=call.tool_name,
                    success=False,
                    status="denied",
                    error=decision.reason,
                ),
                decision,
            )

        if call.tool_name == "patch_file":
            args = PatchFileArgs.model_validate(call.arguments)
            if decision.approval_required and (approval is None or approval.status != "approved"):
                diff = diff_for_patch(args, self.policy)
                return (
                    ToolObservation(
                        action_id=call.action_id,
                        tool_name=call.tool_name,
                        success=False,
                        status="pending_approval",
                        output={"path": args.path, "diff": diff},
                    ),
                    decision,
                )
            if approval is not None:
                self._validate_approval(call, approval, checkpoint_hash, run_id)
            if dry_run:
                return (
                    ToolObservation(
                        action_id=call.action_id,
                        tool_name=call.tool_name,
                        success=True,
                        status="dry_run",
                        output={"path": args.path, "diff": diff_for_patch(args, self.policy)},
                    ),
                    decision,
                )
            return execute_patch_file(call, args, self.policy), decision

        if dry_run and call.tool_name in {"run_tests"}:
            return (
                ToolObservation(
                    action_id=call.action_id,
                    tool_name=call.tool_name,
                    success=True,
                    status="dry_run",
                    output={"skipped": "dry_run"},
                ),
                decision,
            )

        if call.tool_name == "read_file":
            return (
                execute_read_file(call, ReadFileArgs.model_validate(call.arguments), self.policy),
                decision,
            )
        if call.tool_name == "search_code":
            return (
                execute_search_code(
                    call,
                    SearchCodeArgs.model_validate(call.arguments),
                    self.project_root,
                    self.policy,
                ),
                decision,
            )
        if call.tool_name == "run_tests":
            return (
                execute_run_tests(
                    call,
                    RunTestsArgs.model_validate(call.arguments),
                    self.project_root,
                ),
                decision,
            )
        if call.tool_name == "git_status":
            return execute_git_status(call, self.project_root), decision
        raise ValueError(f"unknown tool: {call.tool_name}")

    def proposed_effect_hash(self, call: ToolCall) -> str:
        if call.tool_name == "patch_file":
            args = PatchFileArgs.model_validate(call.arguments)
            return proposed_patch_effect_hash(args, self.policy)
        return sha256_text(call.arguments_hash())

    def _validate_approval(
        self,
        call: ToolCall,
        approval: ApprovalRecord,
        checkpoint_hash: str,
        run_id: str | None,
    ) -> None:
        expected = {
            "run_id": run_id,
            "action_id": call.action_id,
            "tool_name": call.tool_name,
            "arguments_hash": call.arguments_hash(),
            "policy_profile": self.policy.profile.name,
            "checkpoint_hash": checkpoint_hash,
            "proposed_effect_hash": self.proposed_effect_hash(call),
        }
        actual = {
            "run_id": approval.run_id,
            "action_id": approval.action_id,
            "tool_name": approval.tool_name,
            "arguments_hash": approval.arguments_hash,
            "policy_profile": approval.policy_profile,
            "checkpoint_hash": approval.checkpoint_hash,
            "proposed_effect_hash": approval.proposed_effect_hash,
        }
        if actual != expected:
            raise ValueError("approval binding does not match action")
