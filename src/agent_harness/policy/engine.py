from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from agent_harness.config import load_model
from agent_harness.policy.approvals import provider_use_approval
from agent_harness.policy.classifiers import classify_path
from agent_harness.policy.path_sandbox import denied_glob, is_within_roots, resolve_relative
from agent_harness.policy.redaction import compile_redaction_patterns, redact_text
from agent_harness.schemas import (
    PolicyDecision,
    PolicyProfile,
    ProviderInputRuleAction,
    RunProviderRecord,
    Sensitivity,
    TaskSpec,
    ToolCall,
)
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
        self._redaction_patterns = compile_redaction_patterns(profile.redaction_patterns)

    def profile_hash(self) -> str:
        return sha256_json(self.profile.model_dump(mode="json"))

    def allowed_tools_for(self, task: TaskSpec | None) -> set[str]:
        ceiling: set[str] = {tool for tool in self.profile.allowed_tools}
        if task is None or task.allowed_tools is None:
            return ceiling
        return ceiling.intersection({tool for tool in task.allowed_tools})

    def evaluate_path(self, path: str, mode: str, operation: str) -> PolicyDecision:
        try:
            relative = normalize_relative_path(path)
        except ValueError as exc:
            return self._decision(False, False, f"invalid path: {exc}", [operation])

        denied = denied_glob(self.profile, relative)
        if denied:
            return self._decision(
                False, False, f"path denied by glob: {denied}", [operation, denied]
            )

        roots = self.profile.read_roots if mode == "read" else self.profile.write_roots
        if not is_within_roots(self.project_root, relative, roots):
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

    def evaluate_provider_use(
        self, provider: RunProviderRecord, checkpoint_hash: str
    ) -> PolicyDecision:
        matched = [
            f"provider:{provider.provider_profile_id}",
            f"trust_zone:{provider.trust_zone}",
            f"checkpoint:{checkpoint_hash[:12]}",
            f"network_boundary:{str(provider.network).lower()}",
        ]
        trust_action = self.profile.provider_trust_policy.get(provider.trust_zone)
        if trust_action is None:
            return self._decision(False, False, "trust zone not allowed by policy", matched)
        if trust_action == "deny":
            return self._decision(False, False, "provider use denied by trust-zone policy", matched)

        approval_required, reason = provider_use_approval(provider, trust_action)
        if provider.requires_approval:
            matched.append("provider:requires_approval")

        return self._decision(True, approval_required, reason, matched)

    def classify_path(self, path: str | None) -> str:
        return classify_path(self.profile, path)

    def provider_input_action_for(self, sensitivity: Sensitivity) -> ProviderInputRuleAction:
        return self.profile.provider_input_policy.get(sensitivity, "deny")

    def is_hard_denied_sensitivity(self, sensitivity: Sensitivity) -> bool:
        return sensitivity in self.profile.hard_deny_sensitivities

    def evaluate_provider_input(
        self,
        sensitivity: Sensitivity,
        provider: RunProviderRecord,
        path: str | None = None,
        denied_sensitivities: set[Sensitivity] | None = None,
    ) -> tuple[ProviderInputRuleAction, PolicyDecision]:
        matched = [
            f"provider:{provider.provider_profile_id}",
            f"trust_zone:{provider.trust_zone}",
            f"sensitivity:{sensitivity}",
        ]
        if path is not None:
            matched.append(f"path:{path}")
        if denied_sensitivities and sensitivity in denied_sensitivities:
            return (
                "deny",
                self._decision(
                    False,
                    False,
                    f"{sensitivity} denied by task or CLI provider-input narrowing",
                    [*matched, "provider_input:narrowed"],
                ),
            )

        action = self.provider_input_action_for(sensitivity)
        if self.is_hard_denied_sensitivity(sensitivity):
            return (
                action,
                self._decision(
                    False,
                    False,
                    f"{sensitivity} is hard-denied for provider input",
                    [*matched, "provider_input:hard_deny"],
                ),
            )
        if action == "allow":
            return (
                action,
                self._decision(True, False, f"{sensitivity} allowed for provider input", matched),
            )
        if action == "allow_untrusted":
            return (
                action,
                self._decision(
                    True,
                    False,
                    f"{sensitivity} allowed as untrusted provider evidence",
                    [*matched, "provider_input:untrusted"],
                ),
            )
        if action == "approval_required":
            return (
                action,
                self._decision(
                    True,
                    True,
                    f"{sensitivity} requires provider-input approval",
                    [*matched, "provider_input:approval_required"],
                ),
            )
        if action == "redact":
            return (
                action,
                self._decision(
                    True,
                    False,
                    f"{sensitivity} requires provider-input redaction",
                    [*matched, "provider_input:redact"],
                ),
            )
        return (
            action,
            self._decision(False, False, f"{sensitivity} denied by provider-input policy", matched),
        )

    def redact_text(self, text: str) -> tuple[str, list[str]]:
        return redact_text(text, self._redaction_patterns)

    def resolve_relative(self, path: str) -> Path:
        return resolve_relative(self.project_root, path)

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
