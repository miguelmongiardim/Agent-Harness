from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.provider_gateway import ProviderGateway
from agent_harness.schemas import (
    ContextManifest,
    ProviderProfileConfig,
    RunProviderRecord,
    TaskSpec,
    ToolObservation,
)


def _seed_project_with_recorded_openai_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "recorded-openai",
        "provider_profiles": [
            {
                "provider_profile_id": "recorded-openai",
                "transport": "openai_compatible",
                "trust_zone": "local_process",
                "model": "gpt-4o-mini",
                "endpoint_env": "AGENT_HARNESS_RECORDED_OPENAI_ENDPOINT",
                "network": False,
                "requires_approval": False,
                "api_key_env": "AGENT_HARNESS_RECORDED_OPENAI_API_KEY",
            }
        ],
    }
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    policy["sensitivity_rules"] = [
        *policy["sensitivity_rules"],
        {"pattern": "sample.py", "classification": "public"},
    ]
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2),
        encoding="utf-8",
    )


def test_recorded_openai_provider_run_completes_and_records_provider_audit(
    tmp_path: Path,
) -> None:
    _seed_project_with_recorded_openai_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "recorded-openai",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-recorded-openai"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T16:00:00Z"
    env["AGENT_HARNESS_RECORDED_OPENAI_ENDPOINT"] = "recorded://openai_compatible/read_only"
    env["AGENT_HARNESS_RECORDED_OPENAI_API_KEY"] = "gateway-test-secret"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["status"] == "completed"

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-recorded-openai"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    provider_calls = inspected["provider_calls"]["calls"]
    assert provider_calls
    assert provider_calls[0]["transport"] == "openai_compatible"
    assert provider_calls[0]["trust_zone"] == "local_process"
    assert provider_calls[0]["model"] == "gpt-4o-mini"
    assert provider_calls[0]["endpoint_identity"] == "env:AGENT_HARNESS_RECORDED_OPENAI_ENDPOINT"
    assert provider_calls[0]["network"] is False
    assert provider_calls[0]["mode"] == "recorded_fixture"
    assert provider_calls[0]["fixture_id"] == "openai_compatible.read_only"
    assert inspected["artifact_index"]["artifacts"]["provider_calls"].endswith(
        "provider_calls.json"
    )

    run_dir = tmp_path / ".agent-harness" / "runs" / "run-recorded-openai"
    serialized_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in run_dir.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    assert "gateway-test-secret" not in serialized_artifacts


def test_recorded_openai_provider_missing_required_env_var_fails_clearly(
    tmp_path: Path,
) -> None:
    _seed_project_with_recorded_openai_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "missing-provider-env",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-missing-provider-env"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T16:15:00Z"
    env["AGENT_HARNESS_RECORDED_OPENAI_ENDPOINT"] = "recorded://openai_compatible/read_only"
    env.pop("AGENT_HARNESS_RECORDED_OPENAI_API_KEY", None)

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 1
    assert "missing required env var: AGENT_HARNESS_RECORDED_OPENAI_API_KEY" in run.stderr
    assert "gateway-test-secret" not in run.stdout
    assert "gateway-test-secret" not in run.stderr


def _gateway_task() -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "schema_version": "task.v2",
            "task_id": "provider-gateway-contract",
            "title": "Refactor sample",
            "intent": "Refactor add_numbers for clarity",
            "target_paths": ["sample.py"],
            "allowed_tools": ["read_file", "patch_file"],
            "max_steps": 4,
        }
    )


def _gateway_manifest() -> ContextManifest:
    return ContextManifest(
        manifest_id="manifest-provider-gateway",
        run_id="run-provider-gateway",
        task_id="provider-gateway-contract",
    )


def _gateway_read_observation() -> ToolObservation:
    return ToolObservation(
        action_id="read-sample",
        tool_name="read_file",
        success=True,
        status="ok",
        output={
            "path": "sample.py",
            "content": "def add_numbers(a, b):\n    return a + b\n",
        },
    )


@pytest.mark.parametrize(
    (
        "transport",
        "trust_zone",
        "endpoint_env",
        "endpoint_value",
        "api_key_env",
        "fixture_id",
        "mode",
    ),
    [
        ("mock", "mock", "AGENT_HARNESS_GATEWAY_MOCK_ENDPOINT", None, None, None, "mock"),
        (
            "openai_compatible",
            "local_process",
            "AGENT_HARNESS_GATEWAY_OPENAI_ENDPOINT",
            "recorded://openai_compatible/read_only",
            "AGENT_HARNESS_GATEWAY_OPENAI_API_KEY",
            "openai_compatible.read_only",
            "recorded_fixture",
        ),
        (
            "anthropic",
            "local_process",
            "AGENT_HARNESS_GATEWAY_ANTHROPIC_ENDPOINT",
            "recorded://anthropic/read_only",
            "AGENT_HARNESS_GATEWAY_ANTHROPIC_API_KEY",
            "anthropic.read_only",
            "recorded_fixture",
        ),
    ],
)
def test_provider_gateway_contract_is_shared_across_transports(
    monkeypatch,
    transport: str,
    trust_zone: str,
    endpoint_env: str,
    endpoint_value: str | None,
    api_key_env: str | None,
    fixture_id: str | None,
    mode: str,
) -> None:
    if endpoint_value is not None:
        monkeypatch.setenv(endpoint_env, endpoint_value)
    if api_key_env is not None:
        monkeypatch.setenv(api_key_env, "transport-test-secret")

    provider_config = ProviderProfileConfig(
        provider_profile_id=f"{transport}-contract",
        transport=transport,  # type: ignore[arg-type]
        trust_zone=trust_zone,  # type: ignore[arg-type]
        model=f"{transport}-model",
        endpoint_env=endpoint_env,
        network=False,
        requires_approval=False,
        api_key_env=api_key_env,
    )
    provider = RunProviderRecord(
        provider_profile_id=provider_config.provider_profile_id,
        transport=provider_config.transport,
        trust_zone=provider_config.trust_zone,
        model=provider_config.model,
        endpoint_env=provider_config.endpoint_env,
        endpoint_identity=f"env:{provider_config.endpoint_env}",
        network=provider_config.network,
        requires_approval=provider_config.requires_approval,
    )
    gateway = ProviderGateway(Path.cwd())

    initial_actions, initial_audit = gateway.initial_actions(
        "run-provider-gateway",
        _gateway_task(),
        _gateway_manifest(),
        provider,
        provider_config,
        approval_ids=["provider-approval-action"],
    )
    next_actions, next_audit = gateway.next_actions(
        "run-provider-gateway",
        _gateway_task(),
        _gateway_manifest(),
        [_gateway_read_observation()],
        provider,
        provider_config,
        approval_ids=["provider-approval-action"],
    )

    assert initial_actions[0].tool_name == "read_file"
    assert next_actions[0].tool_name == "patch_file"
    assert initial_audit.transport == transport
    assert next_audit.transport == transport
    assert initial_audit.approval_ids == ["provider-approval-action"]
    assert next_audit.approval_ids == ["provider-approval-action"]
    assert initial_audit.mode == mode
    assert next_audit.mode == mode
    assert initial_audit.fixture_id == fixture_id
    assert next_audit.fixture_id == fixture_id
