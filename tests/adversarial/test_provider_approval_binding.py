from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.runtimes.native import HarnessRuntime, approve_action


def test_provider_use_approval_denies_provider_input_hash_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_project_with_local_endpoint_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-input-hash-drift",
                "title": "Inspect target",
                "intent": "Inspect target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-provider-input-hash-drift")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T17:00:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.setenv("AGENT_HARNESS_API_KEY", "approval-binding-secret")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "paused"
    action_id = summary.approvals[0]
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-provider-input-hash-drift"
    provider_input_path = run_dir / "provider_input.json"
    provider_input = json.loads(provider_input_path.read_text(encoding="utf-8"))
    provider_input["records"][0]["content_hash"] = "tampered-provider-input-hash"
    provider_input_path.write_text(json.dumps(provider_input, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="provider-use approval binding"):
        approve_action(
            tmp_path,
            "run-provider-input-hash-drift",
            action_id,
            "approve",
            actor="reviewer",
        )

    provider_calls = json.loads((run_dir / "provider_calls.json").read_text(encoding="utf-8"))
    assert provider_calls["calls"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_profile_id", "other-provider"),
        ("trust_zone", "private_network"),
        ("model", "other-model"),
        ("policy_decision_id", "policy-tampered"),
        ("checkpoint_hash", "checkpoint-tampered"),
    ],
)
def test_provider_use_approval_denies_bound_operation_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    _seed_project_with_local_endpoint_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": f"provider-{field}-drift",
                "title": "Inspect target",
                "intent": "Inspect target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    run_id = f"run-provider-{field.replace('_', '-')}-drift"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", run_id)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T17:05:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.setenv("AGENT_HARNESS_API_KEY", "approval-binding-secret")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "paused"
    action_id = summary.approvals[0]
    run_dir = tmp_path / ".agent-harness" / "runs" / run_id
    action_path = run_dir / "actions" / f"{action_id}.json"
    action = json.loads(action_path.read_text(encoding="utf-8"))
    if field in {"provider_profile_id", "trust_zone", "model"}:
        action["provider"][field] = value
    else:
        action[field] = value
    action_path.write_text(json.dumps(action, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="provider-use approval binding"):
        approve_action(tmp_path, run_id, action_id, "approve", actor="reviewer")

    provider_calls = json.loads((run_dir / "provider_calls.json").read_text(encoding="utf-8"))
    assert provider_calls["calls"] == []


def test_provider_call_artifacts_record_redacted_evidence_without_raw_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_project_with_local_endpoint_provider(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "provider-call-evidence",
                "title": "Inspect target",
                "intent": "Inspect target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-provider-call-evidence")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T17:10:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.setenv("AGENT_HARNESS_API_KEY", "provider-call-secret")

    summary = HarnessRuntime(tmp_path).run_task(task_path)
    action_id = summary.approvals[0]
    approve_action(tmp_path, "run-provider-call-evidence", action_id, "approve", actor="reviewer")

    run_dir = tmp_path / ".agent-harness" / "runs" / "run-provider-call-evidence"
    provider_calls = json.loads((run_dir / "provider_calls.json").read_text(encoding="utf-8"))
    first_call = provider_calls["calls"][0]

    assert first_call["approval_ids"] == [action_id]
    assert first_call["prompt_hash"]
    assert first_call["response_hash"]
    assert first_call["redacted_prompt_summary"] == {
        "kind": "provider_input",
        "records": 1,
        "included_records": 1,
    }
    assert first_call["redacted_response_summary"] == {
        "kind": "tool_calls",
        "tool_calls": first_call["action_count"],
    }
    assert first_call["latency_ms"] >= 0
    assert first_call["token_metrics"]["prompt_records"] == 1
    assert first_call["token_metrics"]["response_actions"] == first_call["action_count"]
    assert first_call["policy_decision_ids"]

    serialized_provider_calls = (run_dir / "provider_calls.json").read_text(encoding="utf-8")
    assert "def identity(value)" not in serialized_provider_calls
    assert "provider-call-secret" not in serialized_provider_calls


def _seed_project_with_local_endpoint_provider(root: Path) -> None:
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
    (root / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
