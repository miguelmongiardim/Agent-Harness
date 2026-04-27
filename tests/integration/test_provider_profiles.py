from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from agent_harness.defaults import DEFAULT_POLICY


def _seed_project_with_provider_profiles(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "mock-default",
        "provider_profiles": [
            {
                "provider_profile_id": "mock-default",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic-default",
                "endpoint_env": "AGENT_HARNESS_MOCK_DEFAULT_ENDPOINT",
                "network": False,
                "requires_approval": False,
            },
            {
                "provider_profile_id": "mock-selected",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic-selected",
                "endpoint_env": "AGENT_HARNESS_MOCK_SELECTED_ENDPOINT",
                "network": False,
                "requires_approval": False,
            },
        ],
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8"
    )


def _run_profile_validation_case(
    tmp_path: Path,
    provider_profile: dict[str, Any],
    env_updates: dict[str, str],
    policy_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": provider_profile["provider_profile_id"],
        "provider_profiles": [provider_profile],
    }
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if policy_updates is not None:
        policy.update(policy_updates)
    policy["sensitivity_rules"] = [
        *policy["sensitivity_rules"],
        {"pattern": "sample.py", "classification": "public"},
    ]
    (tmp_path / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "profile-validation",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-profile-validation"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-27T12:00:00Z"
    env.pop("AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS", None)
    env.update(env_updates)

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-profile-validation"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    return cast(dict[str, Any], json.loads(inspect.stdout))


def _live_openai_profile() -> dict[str, Any]:
    return {
        "provider_profile_id": "live-openai",
        "transport": "openai_compatible",
        "trust_zone": "hosted_provider",
        "model": "gpt-live",
        "endpoint_env": "AGENT_HARNESS_LIVE_ENDPOINT",
        "network": True,
        "requires_approval": True,
        "api_key_env": "AGENT_HARNESS_LIVE_API_KEY",
    }


def test_task_selects_configured_mock_provider_and_records_provider_metadata(
    tmp_path: Path,
) -> None:
    _seed_project_with_provider_profiles(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-profile-selection",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "provider_profile": "mock-selected",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-profile-selection"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["status"] == "dry_run"

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-profile-selection"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    provider = inspected["provider"]
    assert provider["provider_profile_id"] == "mock-selected"
    assert provider["transport"] == "mock"
    assert provider["trust_zone"] == "mock"
    assert provider["model"] == "deterministic-selected"
    assert provider["endpoint_identity"] == "env:AGENT_HARNESS_MOCK_SELECTED_ENDPOINT"
    assert provider["network"] is False
    assert inspected["artifact_index"]["artifacts"]["provider"].endswith("provider.json")


def test_cli_provider_override_switches_to_another_configured_profile(tmp_path: Path) -> None:
    _seed_project_with_provider_profiles(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-profile-override",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "provider_profile": "mock-selected",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-override"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T12:00:00Z"

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "run",
            str(task_path),
            "--provider",
            "mock-default",
            "--dry-run",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-override"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    assert inspected["provider"]["provider_profile_id"] == "mock-default"
    assert inspected["provider"]["model"] == "deterministic-default"


def test_live_openai_compatible_profile_requires_explicit_opt_in_before_provider_use(
    tmp_path: Path,
) -> None:
    inspected = _run_profile_validation_case(
        tmp_path,
        _live_openai_profile(),
        {
            "AGENT_HARNESS_LIVE_ENDPOINT": "https://provider.example.test",
            "AGENT_HARNESS_LIVE_API_KEY": "profile-validation-secret",
        },
    )

    summary = inspected["summary"]
    assert summary["status"] == "failed"
    assert summary["message"] == "provider profile validation failed"
    event_types = [event["type"] for event in inspected["events"]]
    assert "provider_profile_invalid" in event_types
    assert "provider_selected" not in event_types
    assert not any(
        event["type"] == "policy_decision"
        and event["payload"].get("operation") == "provider_use"
        for event in inspected["events"]
    )
    validation_event = next(
        event for event in inspected["events"] if event["type"] == "provider_profile_invalid"
    )
    assert "AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS" in validation_event["payload"]["reason"]
    serialized_artifacts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / ".agent-harness" / "runs" / "run-profile-validation").rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    )
    assert "profile-validation-secret" not in serialized_artifacts


@pytest.mark.parametrize(
    ("provider_profile", "env_updates", "expected_reason"),
    [
        (
            _live_openai_profile(),
            {"AGENT_HARNESS_LIVE_API_KEY": "profile-validation-secret"},
            "missing required env var: AGENT_HARNESS_LIVE_ENDPOINT",
        ),
        (
            {
                key: value
                for key, value in _live_openai_profile().items()
                if key != "api_key_env"
            },
            {"AGENT_HARNESS_LIVE_ENDPOINT": "https://provider.example.test"},
            "requires api_key_env",
        ),
        (
            {**_live_openai_profile(), "network": False},
            {
                "AGENT_HARNESS_LIVE_ENDPOINT": "https://provider.example.test",
                "AGENT_HARNESS_LIVE_API_KEY": "profile-validation-secret",
            },
            "uses a live endpoint but network is false",
        ),
    ],
)
def test_openai_compatible_profile_validation_reports_actionable_diagnostics(
    tmp_path: Path,
    provider_profile: dict[str, Any],
    env_updates: dict[str, str],
    expected_reason: str,
) -> None:
    inspected = _run_profile_validation_case(tmp_path, provider_profile, env_updates)

    validation_event = next(
        event for event in inspected["events"] if event["type"] == "provider_profile_invalid"
    )
    assert expected_reason in validation_event["payload"]["reason"]
    assert "profile-validation-secret" not in json.dumps(inspected)


def test_live_openai_compatible_profile_requires_approval_compatible_policy(
    tmp_path: Path,
) -> None:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    policy["provider_trust_policy"]["hosted_provider"] = "allow"
    policy["trust_zones"]["rules"]["hosted_provider"] = "allow"
    inspected = _run_profile_validation_case(
        tmp_path,
        {**_live_openai_profile(), "requires_approval": False},
        {
            "AGENT_HARNESS_LIVE_ENDPOINT": "https://provider.example.test",
            "AGENT_HARNESS_LIVE_API_KEY": "profile-validation-secret",
            "AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS": "1",
        },
        policy_updates=policy,
    )

    validation_event = next(
        event for event in inspected["events"] if event["type"] == "provider_profile_invalid"
    )
    assert "requires approval-compatible policy" in validation_event["payload"]["reason"]
