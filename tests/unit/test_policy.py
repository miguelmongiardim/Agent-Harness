from __future__ import annotations

from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import PolicyProfile, RunProviderRecord, TaskSpec, ToolCall


def test_task_can_only_narrow_policy_tools(tmp_path: Path) -> None:
    profile = PolicyProfile.model_validate(DEFAULT_POLICY)
    task = TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": "task",
            "title": "Task",
            "intent": "Refactor code",
            "target_paths": ["src/example.py"],
            "allowed_tools": ["patch_file"],
        }
    )
    engine = PolicyEngine(tmp_path, profile)
    read = ToolCall(
        action_id="a1",
        tool_name="read_file",
        arguments={"path": "src/example.py"},
        reason="read",
    )
    patch = ToolCall(
        action_id="a2",
        tool_name="patch_file",
        arguments={"path": "src/example.py", "before_hash": "", "proposed_content": ""},
        reason="patch",
    )

    assert not engine.evaluate_tool_call(read, task, "checkpoint").allowed
    patch_decision = engine.evaluate_tool_call(patch, task, "checkpoint")
    assert patch_decision.allowed
    assert patch_decision.approval_required


def test_policy_denies_traversal_and_denied_globs(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    assert not engine.evaluate_path("../secret.py", "read", "test").allowed
    assert not engine.evaluate_path(".git/config", "read", "test").allowed


def test_policy_sensitivity_defaults(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    assert engine.classify_path("src/public.py") == "internal"
    assert engine.classify_path("config/.env") == "secret"
    assert engine.classify_path(None) == "unknown"


def test_default_provider_input_policy_matrix_matches_defaults(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))
    provider = RunProviderRecord(
        provider_profile_id="mock-default",
        transport="mock",
        trust_zone="mock",
        model="deterministic",
        endpoint_env="AGENT_HARNESS_MOCK_ENDPOINT",
        endpoint_identity="env:AGENT_HARNESS_MOCK_ENDPOINT",
        network=False,
        requires_approval=False,
    )

    public_action, public = engine.evaluate_provider_input(
        "public", provider, path="docs/public.md"
    )
    generated_action, generated = engine.evaluate_provider_input(
        "generated", provider, path="build/generated/output.txt"
    )
    internal_action, internal = engine.evaluate_provider_input(
        "internal", provider, path="src/internal.py"
    )
    confidential_action, confidential = engine.evaluate_provider_input(
        "confidential", provider, path="vault/confidential.md"
    )
    unknown_action, unknown = engine.evaluate_provider_input("unknown", provider)

    assert public_action == "allow"
    assert public.allowed and not public.approval_required
    assert generated_action == "allow_untrusted"
    assert generated.allowed and not generated.approval_required
    assert internal_action == "approval_required"
    assert internal.allowed and internal.approval_required
    assert confidential_action == "deny"
    assert not confidential.allowed
    assert unknown_action == "deny"
    assert not unknown.allowed


def test_provider_profile_requires_approval_can_only_tighten_policy(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))
    provider = RunProviderRecord(
        provider_profile_id="mock-strict",
        transport="mock",
        trust_zone="mock",
        model="deterministic",
        endpoint_env="AGENT_HARNESS_MOCK_ENDPOINT",
        endpoint_identity="env:AGENT_HARNESS_MOCK_ENDPOINT",
        network=False,
        requires_approval=True,
    )

    decision = engine.evaluate_provider_use(provider, "checkpoint-123")

    assert decision.allowed
    assert decision.approval_required


def test_local_process_with_network_boundary_requires_provider_approval(tmp_path: Path) -> None:
    engine = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))
    provider = RunProviderRecord(
        provider_profile_id="local-process-networked",
        transport="openai_compatible",
        trust_zone="local_process",
        model="gpt-test",
        endpoint_env="AGENT_HARNESS_LOCAL_PROCESS_ENDPOINT",
        endpoint_identity="env:AGENT_HARNESS_LOCAL_PROCESS_ENDPOINT",
        network=True,
        requires_approval=False,
    )

    decision = engine.evaluate_provider_use(provider, "checkpoint-123")

    assert decision.allowed
    assert decision.approval_required
