from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY


def _seed_project_with_default_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "local-endpoint",
        "provider_profiles": [
            {
                "provider_profile_id": "local-endpoint",
                "transport": "openai_compatible",
                "trust_zone": "local_endpoint",
                "model": "gpt-test",
                "endpoint_env": "AGENT_HARNESS_LOCAL_ENDPOINT",
                "network": True,
                "requires_approval": False,
                "api_key_env": "AGENT_HARNESS_API_KEY",
            }
        ],
    }
    policy = dict(DEFAULT_POLICY)
    policy["sensitivity_rules"] = [
        *DEFAULT_POLICY["sensitivity_rules"],
        {"pattern": "sample.py", "classification": "public"},
    ]
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")


def test_local_endpoint_provider_pauses_before_model_actions_and_records_pending_approval(
    tmp_path: Path,
) -> None:
    _seed_project_with_default_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-use-approval",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-use-approval"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T12:00:00Z"

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
    assert summary["status"] == "paused"
    assert len(summary["approvals"]) == 1

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-use-approval"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    event_types = [event["type"] for event in inspected["events"]]
    assert "provider_selected" in event_types
    assert "approval_recorded" in event_types
    assert "model_action" not in event_types

    provider_decisions = [
        event["payload"]["decision"]
        for event in inspected["events"]
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "provider_use"
    ]
    assert provider_decisions
    assert provider_decisions[0]["approval_required"] is True

    approval = next(
        event["payload"]["approval"]
        for event in inspected["events"]
        if event["type"] == "approval_recorded"
    )
    assert approval["tool_name"] == "provider_use"
    assert approval["status"] == "pending"


def test_approving_provider_use_resumes_the_same_run(tmp_path: Path) -> None:
    _seed_project_with_default_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-use-resume",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-resume"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T12:00:00Z"
    env["AGENT_HARNESS_LOCAL_ENDPOINT"] = "recorded://openai_compatible/read_only"
    env["AGENT_HARNESS_API_KEY"] = "approval-test-secret"

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
    approval_action_id = summary["approvals"][0]

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "approve",
            "run-provider-resume",
            approval_action_id,
            "--decision",
            "approve",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert approve.returncode == 0, approve.stderr

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-resume"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    assert inspected["summary"]["status"] == "completed"
    assert any(event["type"] == "model_action" for event in inspected["events"])
