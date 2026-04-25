from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ApprovalRecord,
    PolicyDecision,
    TaskSpec,
    ToolCall,
    ToolObservation,
)
from agent_harness.utils import sha256_text, truncate


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReadFileArgs(ToolArgs):
    path: str


class SearchCodeArgs(ToolArgs):
    query: str
    include_globs: list[str] = Field(default_factory=lambda: ["*.py"])
    max_results: int = Field(default=20, ge=1, le=200)


class RunTestsArgs(ToolArgs):
    command: list[str]


class PatchFileArgs(ToolArgs):
    path: str
    before_hash: str
    proposed_content: str


class ToolExecutor:
    def __init__(self, project_root: Path, policy: PolicyEngine) -> None:
        self.project_root = project_root.resolve()
        self.policy = policy

    def execute(
        self,
        call: ToolCall,
        task: TaskSpec | None,
        checkpoint_hash: str,
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
                diff = self._diff_for_patch(args)
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
                self._validate_approval(call, approval, checkpoint_hash)
            if dry_run:
                return (
                    ToolObservation(
                        action_id=call.action_id,
                        tool_name=call.tool_name,
                        success=True,
                        status="dry_run",
                        output={"path": args.path, "diff": self._diff_for_patch(args)},
                    ),
                    decision,
                )
            return self._patch_file(call, args), decision

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
            return self._read_file(call, ReadFileArgs.model_validate(call.arguments)), decision
        if call.tool_name == "search_code":
            return self._search_code(call, SearchCodeArgs.model_validate(call.arguments)), decision
        if call.tool_name == "run_tests":
            return self._run_tests(call, RunTestsArgs.model_validate(call.arguments)), decision
        if call.tool_name == "git_status":
            return self._git_status(call), decision
        raise ValueError(f"unknown tool: {call.tool_name}")

    def proposed_effect_hash(self, call: ToolCall) -> str:
        if call.tool_name == "patch_file":
            args = PatchFileArgs.model_validate(call.arguments)
            return sha256_text(self._diff_for_patch(args) + "\n" + args.proposed_content)
        return sha256_text(call.arguments_hash())

    def _read_file(self, call: ToolCall, args: ReadFileArgs) -> ToolObservation:
        path = self.policy.resolve_relative(args.path)
        content = path.read_text(encoding="utf-8")
        redacted, redactions = self.policy.redact_text(content)
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

    def _search_code(self, call: ToolCall, args: SearchCodeArgs) -> ToolObservation:
        results: list[dict[str, Any]] = []
        ignored = {".git", ".venv", ".agent-harness", "__pycache__"}
        for path in sorted(self.project_root.rglob("*")):
            if not path.is_file() or any(part in ignored for part in path.parts):
                continue
            rel = path.relative_to(self.project_root).as_posix()
            if not any(
                path.match(pattern) or rel.endswith(pattern.removeprefix("*"))
                for pattern in args.include_globs
            ):
                continue
            path_decision = self.policy.evaluate_path(rel, "read", "search_code")
            if not path_decision.allowed:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_no, line in enumerate(lines, start=1):
                if args.query.lower() in line.lower():
                    results.append({"path": rel, "line": line_no, "preview": line.strip()[:200]})
                    if len(results) >= args.max_results:
                        return self._search_observation(call, args.query, results)
        return self._search_observation(call, args.query, results)

    def _search_observation(
        self, call: ToolCall, query: str, results: list[dict[str, Any]]
    ) -> ToolObservation:
        return ToolObservation(
            action_id=call.action_id,
            tool_name=call.tool_name,
            success=True,
            status="ok",
            output={"query": query, "results": results},
        )

    def _run_tests(self, call: ToolCall, args: RunTestsArgs) -> ToolObservation:
        completed = subprocess.run(
            args.command,
            cwd=self.project_root,
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

    def _patch_file(self, call: ToolCall, args: PatchFileArgs) -> ToolObservation:
        path = self.policy.resolve_relative(args.path)
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
                "diff": self._diff(current_content, args.proposed_content, args.path),
            },
        )

    def _git_status(self, call: ToolCall) -> ToolObservation:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.project_root,
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

    def _validate_approval(
        self, call: ToolCall, approval: ApprovalRecord, checkpoint_hash: str
    ) -> None:
        expected = {
            "action_id": call.action_id,
            "tool_name": call.tool_name,
            "arguments_hash": call.arguments_hash(),
            "policy_profile": self.policy.profile.name,
            "checkpoint_hash": checkpoint_hash,
            "proposed_effect_hash": self.proposed_effect_hash(call),
        }
        actual = {
            "action_id": approval.action_id,
            "tool_name": approval.tool_name,
            "arguments_hash": approval.arguments_hash,
            "policy_profile": approval.policy_profile,
            "checkpoint_hash": approval.checkpoint_hash,
            "proposed_effect_hash": approval.proposed_effect_hash,
        }
        if actual != expected:
            raise ValueError("approval binding does not match action")

    def _diff_for_patch(self, args: PatchFileArgs) -> str:
        path = self.policy.resolve_relative(args.path)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._diff(current, args.proposed_content, args.path)

    def _diff(self, before: str, after: str, path: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
