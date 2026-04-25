from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Iterable
from pathlib import Path

from agent_harness.config import load_model
from agent_harness.schemas import PolicyDecision, PolicyProfile, TaskSpec, ToolCall
from agent_harness.utils import normalize_relative_path, sha256_json, stable_id


class PolicyError(RuntimeError):
    pass


def load_policy(root: Path, name: str) -> PolicyProfile:
    path = root / "policies" / f"{name}.json"
    if not path.exists():
        raise PolicyError(f"policy profile not found: {name}")
    return load_model(path, PolicyProfile)


class PolicyEngine:
    def __init__(self, project_root: Path, profile: PolicyProfile) -> None:
        self.project_root = project_root.resolve()
        self.profile = profile
        self._redaction_patterns = [re.compile(pattern) for pattern in profile.redaction_patterns]

    def profile_hash(self) -> str:
        return sha256_json(self.profile.model_dump(mode="json"))

    def allowed_tools_for(self, task: TaskSpec | None) -> set[str]:
        ceiling = set(self.profile.allowed_tools)
        if task is None or task.allowed_tools is None:
            return ceiling
        return ceiling.intersection(task.allowed_tools)

    def evaluate_path(self, path: str, mode: str, operation: str) -> PolicyDecision:
        try:
            relative = normalize_relative_path(path)
        except ValueError as exc:
            return self._decision(False, False, f"invalid path: {exc}", [operation])

        denied = self._denied_globs(relative)
        if denied:
            return self._decision(
                False, False, f"path denied by glob: {denied}", [operation, denied]
            )

        roots = self.profile.read_roots if mode == "read" else self.profile.write_roots
        if not self._is_within_roots(relative, roots):
            return self._decision(False, False, f"path outside {mode} roots", [operation])
        return self._decision(True, False, "path allowed", [operation])

    def evaluate_context_source(self, path: str) -> PolicyDecision:
        decision = self.evaluate_path(path, "read", "context_source")
        if not decision.allowed:
            return decision
        return decision.model_copy(
            update={
                "decision_id": stable_id("policy", "context", path),
                "reason": "context source allowed",
            }
        )

    def evaluate_tool_call(
        self,
        call: ToolCall,
        task: TaskSpec | None,
        checkpoint_hash: str,
    ) -> PolicyDecision:
        matched = [f"tool:{call.tool_name}", f"checkpoint:{checkpoint_hash[:12]}"]
        if call.tool_name not in self.allowed_tools_for(task):
            return self._decision(False, False, "tool not allowed by effective policy", matched)

        path_mode = self._path_mode_for_tool(call.tool_name)
        if path_mode:
            raw_path = call.arguments.get("path")
            if not isinstance(raw_path, str):
                return self._decision(False, False, "tool path argument is required", matched)
            path_decision = self.evaluate_path(raw_path, path_mode, f"tool:{call.tool_name}")
            if not path_decision.allowed:
                return path_decision.model_copy(
                    update={"decision_id": stable_id("policy", call.model_dump(mode="json"))}
                )
            matched.extend(path_decision.matched_rules)

        if call.tool_name == "run_tests":
            command = call.arguments.get("command")
            if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
                return self._decision(
                    False, False, "run_tests command must be an argv array", matched
                )
            if command not in self.profile.allowed_test_commands:
                return self._decision(False, False, "test command not allowed by policy", matched)
            if task is not None and task.test_commands and command not in task.test_commands:
                return self._decision(False, False, "test command not allowed by task", matched)

        approval_required = call.tool_name in self.profile.approval_required_tools
        return self._decision(True, approval_required, "tool call allowed", matched)

    def classify_path(self, path: str) -> str:
        relative = path.replace("\\", "/")
        for rule in self.profile.sensitivity_rules:
            if fnmatch.fnmatch(relative, rule.pattern):
                return rule.classification
        return "public"

    def redact_text(self, text: str) -> tuple[str, list[str]]:
        redactions: list[str] = []
        redacted = text
        for index, pattern in enumerate(self._redaction_patterns):
            if pattern.search(redacted):
                redacted = pattern.sub("[REDACTED]", redacted)
                redactions.append(f"redaction_pattern:{index}")
        return redacted, redactions

    def resolve_relative(self, path: str) -> Path:
        relative = normalize_relative_path(path)
        return (self.project_root / relative).resolve()

    def _decision(
        self,
        allowed: bool,
        approval_required: bool,
        reason: str,
        matched_rules: Iterable[str],
    ) -> PolicyDecision:
        return PolicyDecision(
            decision_id=stable_id(
                "policy",
                self.profile.name,
                allowed,
                approval_required,
                reason,
                list(matched_rules),
            ),
            allowed=allowed,
            approval_required=approval_required,
            reason=reason,
            matched_rules=list(matched_rules),
        )

    def _path_mode_for_tool(self, tool_name: str) -> str | None:
        if tool_name == "read_file":
            return "read"
        if tool_name == "patch_file":
            return "write"
        return None

    def _denied_globs(self, relative: str) -> str | None:
        for pattern in self.profile.deny_globs:
            if self._matches_glob(relative, pattern):
                return pattern
        return None

    def _matches_glob(self, relative: str, pattern: str) -> bool:
        normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(relative, normalized):
            return True
        return normalized.startswith("**/") and fnmatch.fnmatch(relative, normalized[3:])

    def _is_within_roots(self, relative: str, roots: list[str]) -> bool:
        target = (self.project_root / relative).resolve()
        for root in roots:
            root_path = (self.project_root / root).resolve()
            try:
                if os.path.commonpath([str(target), str(root_path)]) == str(root_path):
                    return True
            except ValueError:
                continue
        return False
