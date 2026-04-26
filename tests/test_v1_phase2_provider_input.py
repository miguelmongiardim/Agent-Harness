from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY


def _seed_v2_project_with_mock_provider(root: Path) -> None:
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
                "model": "deterministic-v1",
                "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
                "network": False,
                "requires_approval": False,
            }
        ],
    }
    policy = dict(DEFAULT_POLICY)
    policy["sensitivity_rules"] = [
        {"pattern": "docs/public.md", "classification": "public"},
        {"pattern": "build/generated/**", "classification": "generated"},
        {"pattern": "vault/confidential.md", "classification": "confidential"},
    ]
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2),
        encoding="utf-8",
    )


def _seed_v2_project_with_local_endpoint_provider(root: Path) -> None:
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
            }
        ],
    }
    policy = dict(DEFAULT_POLICY)
    policy["sensitivity_rules"] = [
        {"pattern": "vault/customer.md", "classification": "customer"},
    ]
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2),
        encoding="utf-8",
    )


def test_mock_provider_run_records_mixed_sensitivity_provider_input_evidence(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_mock_provider(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "public.md").write_text("# Public\n\nsafe to share\n", encoding="utf-8")
    (tmp_path / "build" / "generated").mkdir(parents=True)
    (tmp_path / "build" / "generated" / "output.txt").write_text(
        "generated summary\n",
        encoding="utf-8",
    )
    (tmp_path / "vault").mkdir()
    (tmp_path / "vault" / "confidential.md").write_text(
        "# Confidential\n\nfor internal only\n",
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-provider-input",
                "title": "Record provider input evidence",
                "intent": "Inspect target files without changing them.",
                "target_paths": [
                    "docs/public.md",
                    "build/generated/output.txt",
                    "vault/confidential.md",
                ],
                "allowed_tools": ["read_file"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-input-phase2"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T14:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-input-phase2"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    provider_input = inspected["provider_input"]
    assert provider_input["provider_profile_id"] == "mock-default"
    assert provider_input["trust_zone"] == "mock"

    records_by_path = {record["path"]: record for record in provider_input["records"]}
    assert records_by_path["docs/public.md"]["policy_action"] == "allow"
    assert records_by_path["docs/public.md"]["included"] is True
    assert records_by_path["docs/public.md"]["untrusted"] is False
    assert records_by_path["build/generated/output.txt"]["policy_action"] == "allow_untrusted"
    assert records_by_path["build/generated/output.txt"]["included"] is True
    assert records_by_path["build/generated/output.txt"]["untrusted"] is True
    assert records_by_path["vault/confidential.md"]["policy_action"] == "deny"
    assert records_by_path["vault/confidential.md"]["included"] is False

    provider_input_decisions = [
        event["payload"]
        for event in inspected["events"]
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "provider_input"
    ]
    assert {decision["path"] for decision in provider_input_decisions} == {
        "docs/public.md",
        "build/generated/output.txt",
        "vault/confidential.md",
    }


def test_internal_provider_input_requires_distinct_approval_and_resume(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_mock_provider(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "internal.py").write_text(
        "def internal_only() -> str:\n    return 'internal'\n",
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-provider-input-approval",
                "title": "Pause for provider input approval",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["src/internal.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-input-approval"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T14:30:00Z"

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
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-input-approval"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    record = inspected["provider_input"]["records"][0]
    assert record["path"] == "src/internal.py"
    assert record["policy_action"] == "approval_required"
    assert record["included"] is False
    assert record["approval_id"] == summary["approvals"][0]
    assert not any(event["type"] == "model_action" for event in inspected["events"])

    approval = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "approve",
            "run-provider-input-approval",
            summary["approvals"][0],
            "--decision",
            "approve",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert approval.returncode == 0, approval.stderr

    resumed = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-input-approval"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resumed.returncode == 0, resumed.stderr
    resumed_payload = json.loads(resumed.stdout)
    resumed_record = resumed_payload["provider_input"]["records"][0]
    assert resumed_payload["summary"]["status"] == "completed"
    assert resumed_record["included"] is True
    assert resumed_record["approval_id"] == summary["approvals"][0]
    assert any(event["type"] == "model_action" for event in resumed_payload["events"])


def test_task_spec_can_narrow_provider_input_permissions(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_mock_provider(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "public.md").write_text("# Public\n\nsafe to share\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-task-narrowing",
                "title": "Narrow provider input",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["docs/public.md"],
                "allowed_tools": ["read_file"],
                "deny_provider_input_sensitivities": ["public"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-task-provider-input-narrowing"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T15:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "inspect",
            "run",
            "run-task-provider-input-narrowing",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    record = inspected["provider_input"]["records"][0]
    assert record["path"] == "docs/public.md"
    assert record["policy_action"] == "deny"
    assert record["included"] is False


def test_cli_can_narrow_provider_input_permissions(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_mock_provider(tmp_path)
    (tmp_path / "build" / "generated").mkdir(parents=True)
    (tmp_path / "build" / "generated" / "output.txt").write_text(
        "generated summary\n",
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-cli-narrowing",
                "title": "Narrow provider input from CLI",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["build/generated/output.txt"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-cli-provider-input-narrowing"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T15:15:00Z"

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "run",
            str(task_path),
            "--dry-run",
            "--deny-provider-input",
            "generated",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "inspect",
            "run",
            "run-cli-provider-input-narrowing",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    record = inspected["provider_input"]["records"][0]
    assert record["path"] == "build/generated/output.txt"
    assert record["policy_action"] == "deny"
    assert record["included"] is False


def test_provider_use_approval_cannot_override_hard_denied_provider_input(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_local_endpoint_provider(tmp_path)
    (tmp_path / "vault").mkdir()
    (tmp_path / "vault" / "customer.md").write_text(
        "# Customer\n\naccount data\n",
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-hard-deny",
                "title": "Keep customer data out of provider input",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["vault/customer.md"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-hard-deny"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T15:30:00Z"
    env["AGENT_HARNESS_LOCAL_ENDPOINT"] = "recorded://openai_compatible/read_only_v1"

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

    approve = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "approve",
            "run-provider-hard-deny",
            summary["approvals"][0],
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
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-hard-deny"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    record = inspected["provider_input"]["records"][0]
    assert inspected["summary"]["status"] == "completed"
    assert record["path"] == "vault/customer.md"
    assert record["policy_action"] == "deny"
    assert record["included"] is False
    assert "hard-denied" in record["policy_reason"]


def test_provider_input_redaction_reclassification_and_reevaluation_are_recorded(
    tmp_path: Path,
) -> None:
    _seed_v2_project_with_mock_provider(tmp_path)
    policy_path = tmp_path / "policies" / "default.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["sensitivity_rules"] = [
        {"pattern": "vault/confidential.md", "classification": "confidential"},
    ]
    policy["provider_input_policy"]["confidential"] = "redact"
    policy["provider_input_redact_reclassify"] = {"confidential": "public"}
    policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    (tmp_path / "vault").mkdir()
    (tmp_path / "vault" / "confidential.md").write_text(
        "token = visible-secret\n",
        encoding="utf-8",
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "phase2-redact-reclassify",
                "title": "Redact provider input",
                "intent": "Inspect target files without changing them.",
                "target_paths": ["vault/confidential.md"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-provider-redact"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T15:45:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-provider-redact"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    record = inspected["provider_input"]["records"][0]
    assert record["path"] == "vault/confidential.md"
    assert record["included"] is True
    assert record["effective_sensitivity"] == "public"
    assert record["policy_action"] == "allow"
    assert record["redaction_status"] == "reclassified"
    assert record["redactions_applied"]
    assert "[REDACTED]" in record["text"]
    assert "visible-secret" not in record["text"]
