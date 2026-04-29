from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest

from agent_harness.context.schema import ContextManifest
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.model.adapters import ProviderEnvelopeValidationError, ProviderGateway
from agent_harness.model.schema import (
    ProviderProfileConfig,
    RunProviderRecord,
)
from agent_harness.tasks.schema import TaskSpec
from agent_harness.tools.schema import ToolObservation

pytestmark = pytest.mark.slow


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

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["status"] == "failed"
    assert summary["message"] == "provider profile validation failed"

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "inspect",
            "run",
            "run-missing-provider-env",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    validation_event = next(
        event for event in inspected["events"] if event["type"] == "provider_profile_invalid"
    )
    assert (
        "missing required env var: AGENT_HARNESS_RECORDED_OPENAI_API_KEY"
        in validation_event["payload"]["reason"]
    )
    assert "gateway-test-secret" not in run.stdout
    assert "gateway-test-secret" not in run.stderr


def test_recorded_provider_invalid_envelope_fails_before_tool_execution(
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
                "task_id": "invalid-provider-envelope",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-invalid-provider-envelope"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T16:30:00Z"
    env["AGENT_HARNESS_RECORDED_OPENAI_ENDPOINT"] = "recorded://openai_compatible/invalid_envelope"
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
    assert summary["status"] == "failed"
    assert summary["message"] == "provider envelope validation failed"

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "inspect",
            "run",
            "run-invalid-provider-envelope",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    event_types = [event["type"] for event in inspected["events"]]
    assert "provider_envelope_rejected" in event_types
    assert "model_action" not in event_types
    assert "tool_observation" not in event_types
    provider_calls = inspected["provider_calls"]["calls"]
    assert provider_calls[0]["redacted_response_summary"] == {
        "kind": "provider_envelope_validation_error",
        "schema_version": "provider_action_envelope.v1",
    }
    assert provider_calls[0]["action_envelope_hash"]
    assert provider_calls[0]["checkpoint_hash"]
    response_artifact = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-invalid-provider-envelope"
            / provider_calls[0]["redacted_response_artifact"]
        ).read_text(encoding="utf-8")
    )
    assert response_artifact["schema_version"] == "provider_redacted_response.v1"
    assert response_artifact["kind"] == "provider_envelope_validation_error"
    assert response_artifact["envelope"] == {
        "schema_version": "provider_action_envelope.v1",
        "kind": "provider_envelope_validation_error",
    }
    serialized_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agent-harness" / "runs" / "run-invalid-provider-envelope").rglob(
            "*"
        )
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    assert "gateway-test-secret" not in serialized_artifacts


def test_live_provider_transport_uses_documented_opt_in_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint_env = "AGENT_HARNESS_LIVE_TEST_ENDPOINT"
    api_key_env = "AGENT_HARNESS_LIVE_TEST_API_KEY"
    monkeypatch.setenv(endpoint_env, "https://provider.example.test")
    monkeypatch.setenv(api_key_env, "live-test-secret")

    provider_config = ProviderProfileConfig(
        provider_profile_id="live-contract",
        transport="openai_compatible",
        trust_zone="hosted_provider",
        model="live-model",
        endpoint_env=endpoint_env,
        network=True,
        requires_approval=True,
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

    with pytest.raises(ValueError, match="live provider transport is disabled"):
        gateway.initial_actions(
            "run-live-provider-disabled",
            _gateway_task(),
            _gateway_manifest(),
            provider,
            provider_config,
        )

    monkeypatch.setenv("AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS", "1")
    with _openai_compatible_server(
        [
            {
                "schema_version": "provider_action_envelope.v1",
                "kind": "actions",
                "actions": [
                    {
                        "schema_version": "tool_call.v1",
                        "action_id": "live-read-sample",
                        "tool_name": "read_file",
                        "arguments": {"path": "sample.py"},
                        "reason": "inspect target file",
                    }
                ],
            }
        ]
    ) as endpoint:
        monkeypatch.setenv(endpoint_env, endpoint)
        actions, audit = gateway.initial_actions(
            "run-live-provider-opted-in",
            _gateway_task(),
            _gateway_manifest(),
            provider,
            provider_config,
        )

    assert actions[0].tool_name == "read_file"
    assert audit.mode == "live_smoke"
    assert audit.fixture_id is None


def test_live_openai_compatible_smoke_completes_with_auto_approval(
    tmp_path: Path,
) -> None:
    _seed_project_with_live_openai_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "live-openai-smoke",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )

    with _openai_compatible_server(
        [
            {
                "schema_version": "provider_action_envelope.v1",
                "kind": "actions",
                "actions": [
                    {
                        "schema_version": "tool_call.v1",
                        "action_id": "live-read-sample",
                        "tool_name": "read_file",
                        "arguments": {"path": "sample.py"},
                        "reason": "inspect target file",
                    }
                ],
            },
            {
                "schema_version": "provider_action_envelope.v1",
                "kind": "actions",
                "actions": [],
            },
        ]
    ) as endpoint:
        env = os.environ.copy()
        env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-live-openai-smoke"
        env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-27T13:00:00Z"
        env["AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS"] = "1"
        env["AGENT_HARNESS_LIVE_OPENAI_ENDPOINT"] = endpoint
        env["AGENT_HARNESS_LIVE_OPENAI_API_KEY"] = "live-smoke-secret"

        run = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_harness",
                "run",
                str(task_path),
                "--auto-approve",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert run.returncode == 0, run.stderr
        assert _OpenAICompatibleHandler.request_count == 2

    summary = json.loads(run.stdout)
    assert summary["status"] == "completed"
    assert summary["approvals"]

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-live-openai-smoke"],
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
    assert {call["mode"] for call in provider_calls} == {"live_smoke"}
    assert provider_calls[0]["approval_ids"] == summary["approvals"]
    assert provider_calls[0]["redacted_response_summary"]["kind"] == "tool_calls"
    assert any(event["type"] == "model_action" for event in inspected["events"])
    serialized_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agent-harness" / "runs" / "run-live-openai-smoke").rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    assert "live-smoke-secret" not in serialized_artifacts


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


def _seed_project_with_live_openai_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "live-openai",
        "provider_profiles": [
            {
                "provider_profile_id": "live-openai",
                "transport": "openai_compatible",
                "trust_zone": "hosted_provider",
                "model": "live-model",
                "endpoint_env": "AGENT_HARNESS_LIVE_OPENAI_ENDPOINT",
                "network": True,
                "requires_approval": True,
                "api_key_env": "AGENT_HARNESS_LIVE_OPENAI_API_KEY",
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


class _OpenAICompatibleHandler(BaseHTTPRequestHandler):
    response_payloads: list[dict[str, Any]] = []
    request_count = 0

    def do_POST(self) -> None:
        type(self).request_count += 1
        payload = type(self).response_payloads.pop(0)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(payload),
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 5,
                        "completion_tokens": 7,
                        "total_tokens": 12,
                    },
                }
            ).encode("utf-8")
        )

    def log_message(self, format: str, *args: object) -> None:
        return


class _openai_compatible_server:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        _OpenAICompatibleHandler.response_payloads = list(self.responses)
        _OpenAICompatibleHandler.request_count = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenAICompatibleHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = cast(tuple[str, int], self.server.server_address)
        return f"http://{host}:{port}"

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=5)


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
    ("fixture_name", "expected_kind"),
    [
        ("invalid_arguments", "provider_envelope_validation_error"),
        ("refusal", "provider_envelope_validation_error"),
        ("unsupported", "provider_envelope_validation_error"),
    ],
)
def test_recorded_provider_rejects_invalid_refusal_and_unsupported_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    fixture_name: str,
    expected_kind: str,
) -> None:
    endpoint_env = "AGENT_HARNESS_GATEWAY_INVALID_ENVELOPE_ENDPOINT"
    api_key_env = "AGENT_HARNESS_GATEWAY_INVALID_ENVELOPE_API_KEY"
    monkeypatch.setenv(endpoint_env, f"recorded://openai_compatible/{fixture_name}")
    monkeypatch.setenv(api_key_env, "transport-test-secret")

    provider_config = ProviderProfileConfig(
        provider_profile_id="invalid-envelope-contract",
        transport="openai_compatible",
        trust_zone="local_process",
        model="openai_compatible-model",
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

    with pytest.raises(ProviderEnvelopeValidationError) as exc_info:
        gateway.initial_actions(
            "run-provider-gateway",
            _gateway_task(),
            _gateway_manifest(),
            provider,
            provider_config,
        )

    assert exc_info.value.audit.redacted_response_summary["kind"] == expected_kind
    assert exc_info.value.audit.action_count == 0


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
    monkeypatch: pytest.MonkeyPatch,
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
