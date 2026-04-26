from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY


def _seed_v2_project(root: Path) -> None:
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


def test_v2_task_selects_configured_mock_provider_and_records_provider_metadata(
    tmp_path: Path,
) -> None:
    _seed_v2_project(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase0-provider-profile",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-phase0"
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
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-phase0"],
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
    _seed_v2_project(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase0-provider-override",
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
