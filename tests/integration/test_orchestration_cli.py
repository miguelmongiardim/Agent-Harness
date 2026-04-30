from __future__ import annotations

import copy
import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from tests.conftest import seed_project


def _write_orchestration_policy(root: Path, *, classify_sample: bool = False) -> None:
    (root / "policies").mkdir(exist_ok=True)
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    if classify_sample:
        policy["sensitivity_rules"] = [
            *policy["sensitivity_rules"],
            {"pattern": "sample.py", "classification": "public"},
        ]
    (root / "policies" / "default.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")


def _write_provider_config(
    root: Path,
    provider_profiles: list[dict[str, object]],
    *,
    default_provider_profile: str | None = None,
) -> None:
    config: dict[str, object] = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "provider_profiles": provider_profiles,
    }
    if default_provider_profile is not None:
        config["default_provider_profile"] = default_provider_profile
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _mock_provider_profile() -> dict[str, object]:
    return {
        "provider_profile_id": "mock-default",
        "transport": "mock",
        "trust_zone": "mock",
        "model": "mock-model",
        "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
        "network": False,
        "requires_approval": False,
    }


def _local_endpoint_provider_profile() -> dict[str, object]:
    return {
        "provider_profile_id": "local-endpoint",
        "transport": "openai_compatible",
        "trust_zone": "local_endpoint",
        "model": "gpt-test",
        "endpoint_env": "AGENT_HARNESS_LOCAL_ENDPOINT",
        "network": True,
        "requires_approval": False,
        "api_key_env": "AGENT_HARNESS_API_KEY",
    }


def _write_sample_py(root: Path) -> None:
    (root / "sample.py").write_text("def identity(value):\n    return value\n", encoding="utf-8")


def _write_provider_dependency_spec(
    root: Path,
    *,
    orchestration_id: str,
    filename: str,
    title: str,
    reviewer_intent: str,
) -> Path:
    spec_path = root / filename
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": orchestration_id,
                "title": title,
                "children": [
                    {
                        "child_id": "provider",
                        "role": "planner",
                        "title": "Provider-backed planner",
                        "intent": "Inspect the target with explicit provider use.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                        "provider_profile": "local-endpoint",
                    },
                    {
                        "child_id": "reviewer",
                        "role": "reviewer",
                        "title": "Review provider output",
                        "intent": reviewer_intent,
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                        "depends_on": ["provider"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return spec_path


def _approve_orchestration_plan(capsys, orchestration_id: str, action_id: str) -> None:  # type: ignore[no-untyped-def]
    assert (
        main(
            [
                "orchestration",
                "approve",
                orchestration_id,
                action_id,
                "--decision",
                "approve",
            ]
        )
        == 0
    )
    capsys.readouterr()


def test_orchestration_run_help_is_discoverable(capsys) -> None:  # type: ignore[no-untyped-def]
    try:
        main(["orchestration", "run", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()
    assert "usage: agent-harness orchestration run" in captured.out
    assert "--dry-run" in captured.out
    assert "spec_path" in captured.out


def test_orchestration_run_denies_missing_policy_section_without_child_runs(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    spec_path = tmp_path / "orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "missing-policy",
                "title": "Missing policy section",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Plan",
                        "intent": "Plan without mutation.",
                        "target_paths": ["README.md"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert "policy.v2.orchestration" in captured.err
    assert "missing" in captured.err
    assert not (tmp_path / ".agent-harness" / "runs").exists()
    assert not (tmp_path / ".agent-harness" / "orchestrations").exists()


def test_orchestration_run_reports_invalid_spec_before_policy_denial(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    spec_path = tmp_path / "invalid-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "invalid",
                "title": "Invalid",
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 2
    captured = capsys.readouterr()
    assert "children" in captured.err
    assert "Field required" in captured.err
    assert "policy.v2.orchestration" not in captured.err


def test_orchestration_run_and_inspect_one_readonly_planner_child(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v11-phase2-planner")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T08:00:00Z")
    seed_project(tmp_path)
    (tmp_path / "sample.py").write_text(
        "def identity(value):\n    return value\n", encoding="utf-8"
    )
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "minimal-readonly",
                "title": "Minimal read-only orchestration",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Inspect target",
                        "intent": "Inspect the target without changing files.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)

    assert summary["schema_version"] == "orchestration_summary.v1"
    assert summary["orchestration_id"] == "minimal-readonly"
    assert summary["status"] == "dry_run"
    assert summary["policy_profile"] == "default"
    assert summary["events_count"] >= 4
    assert len(summary["children"]) == 1
    child = summary["children"][0]
    assert child["child_id"] == "planner"
    assert child["role"] == "planner"
    assert child["status"] == "dry_run"
    assert child["run_id"] == "run-v11-phase2-planner"
    assert child["task_id"] == "minimal-readonly-planner"
    assert child["materialized_task_path"].endswith("children/planner.task.json")
    assert child["run_summary_artifact"].endswith(
        ".agent-harness/runs/run-v11-phase2-planner/summary.json"
    )

    orchestration_dir = tmp_path / ".agent-harness" / "orchestrations" / "minimal-readonly"
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-v11-phase2-planner"
    assert orchestration_dir.is_dir()
    assert run_dir.is_dir()
    materialized_task = json.loads(
        (orchestration_dir / "children" / "planner.task.json").read_text(encoding="utf-8")
    )
    assert materialized_task["schema_version"] == "task.v2"
    assert materialized_task["task_id"] == "minimal-readonly-planner"
    assert materialized_task["policy_profile"] == "default"
    assert materialized_task["allowed_tools"] == ["read_file"]

    assert main(["orchestration", "inspect", "minimal-readonly"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["summary"] == summary
    assert inspected["manifest"]["orchestration_id"] == "minimal-readonly"
    assert inspected["artifact_index"]["artifacts"]["summary"].endswith(
        "orchestrations/minimal-readonly/summary.json"
    )
    assert len(inspected["events"]) == summary["events_count"]
    assert inspected["events"][0]["type"] == "orchestration_started"
    assert inspected["events"][-1]["type"] == "orchestration_finished"


def test_orchestration_export_references_child_artifacts_without_raw_provider_payloads(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v11-phase6-export")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T13:00:00Z")
    seed_project(tmp_path)
    _write_orchestration_policy(tmp_path)
    _write_sample_py(tmp_path)
    spec_path = tmp_path / "export-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "export-safe",
                "title": "Export safe orchestration",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Inspect target",
                        "intent": "Inspect the target without changing files.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    child_run_id = summary["children"][0]["run_id"]
    child_run_dir = tmp_path / ".agent-harness" / "runs" / child_run_id
    (child_run_dir / "provider_calls.json").write_text(
        json.dumps(
            {
                "schema_version": "provider_calls.v1",
                "calls": [
                    {
                        "raw_request": {"messages": ["do-not-copy-export-secret"]},
                        "raw_response": {"text": "do-not-copy-export-secret"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "export", "export-safe"]) == 0
    export_path = Path(capsys.readouterr().out.strip())
    exported = json.loads((tmp_path / export_path).read_text(encoding="utf-8"))
    serialized = json.dumps(exported)

    assert export_path.as_posix() == ".agent-harness/exports/export-safe.orchestration.json"
    assert exported["schema_version"] == "orchestration_export.v1"
    assert exported["orchestration_id"] == "export-safe"
    assert exported["summary"]["schema_version"] == "orchestration_summary.v1"
    assert exported["manifest"]["schema_version"] == "orchestration_manifest.v1"
    assert exported["artifact_index"]["schema_version"] == "orchestration_artifact_index.v1"
    assert exported["child_artifacts"] == [
        {
            "child_id": "planner",
            "run_id": child_run_id,
            "run_summary_artifact": f".agent-harness/runs/{child_run_id}/summary.json",
            "run_artifact_index": f".agent-harness/runs/{child_run_id}/artifact-index.json",
            "materialized_task_path": (
                ".agent-harness/orchestrations/export-safe/children/planner.task.json"
            ),
        }
    ]
    assert "provider_calls" not in serialized
    assert "raw_request" not in serialized
    assert "raw_response" not in serialized
    assert "do-not-copy-export-secret" not in serialized
    assert str(tmp_path) not in serialized


def test_orchestration_mcp_resources_list_and_read_safe_summary(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v11-phase6-mcp-summary")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T13:30:00Z")
    seed_project(tmp_path)
    _write_orchestration_policy(tmp_path)
    _write_sample_py(tmp_path)
    spec_path = tmp_path / "mcp-summary-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "mcp-summary",
                "title": "MCP summary orchestration",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Inspect target",
                        "intent": "Inspect the target without changing files.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)

    assert main(["mcp", "resources", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in listed["resources"]}

    assert "agent-harness://orchestrations" in resource_uris
    assert "agent-harness://orchestrations/mcp-summary/summary" in resource_uris
    assert "agent-harness://orchestrations/mcp-summary/tools" not in resource_uris

    assert (
        main(
            [
                "mcp",
                "resources",
                "read",
                "agent-harness://orchestrations/mcp-summary/summary",
                "--json",
            ]
        )
        == 0
    )
    envelope = json.loads(capsys.readouterr().out)
    record = json.loads(
        (tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl").read_text(encoding="utf-8")
    )

    assert envelope["schema_version"] == "mcp_resource_envelope.v1"
    assert envelope["uri"] == "agent-harness://orchestrations/mcp-summary/summary"
    assert envelope["resource_type"] == "orchestration_summary"
    assert envelope["source_artifact"] == ".agent-harness/orchestrations/mcp-summary/summary.json"
    assert envelope["source_schema_version"] == "orchestration_summary.v1"
    assert envelope["policy_profile"] == "default"
    assert envelope["denial_status"] == "allowed"
    assert envelope["content"] == summary
    assert envelope["metadata"]["orchestration_id"] == "mcp-summary"
    assert str(tmp_path) not in json.dumps(envelope)

    assert record["schema_version"] == "mcp_access_log.v1"
    assert record["request_type"] == "resource_read"
    assert record["resource_uri"] == "agent-harness://orchestrations/mcp-summary/summary"
    assert record["orchestration_id"] == "mcp-summary"
    assert record["artifact_type"] == "orchestration_summary"
    assert record["policy_profile"] == "default"
    assert record["result"] == "allowed"
    assert record["redaction_applied"] is False
    assert record["denial_reason"] is None
    assert "content" not in record
    assert "MCP summary orchestration" not in json.dumps(record)


def test_orchestration_mcp_reads_core_artifacts_as_safe_envelopes(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T14:00:00Z")
    seed_project(tmp_path)
    _write_orchestration_policy(tmp_path)
    _write_sample_py(tmp_path)
    spec_path = tmp_path / "mcp-core-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "mcp-core",
                "title": "MCP core orchestration",
                "children": [
                    {
                        "child_id": "reviewer",
                        "role": "reviewer",
                        "title": "Review handoff",
                        "intent": "Review the generated handoff.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                        "depends_on": ["planner"],
                    },
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Plan work",
                        "intent": "Inspect the target and produce a handoff.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert main(["mcp", "resources", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in listed["resources"]}
    expected = {
        "agent-harness://orchestrations/mcp-core/manifest",
        "agent-harness://orchestrations/mcp-core/events",
        "agent-harness://orchestrations/mcp-core/children",
        "agent-harness://orchestrations/mcp-core/handoffs",
    }

    assert expected <= resource_uris

    read = {}
    for uri in sorted(expected):
        assert main(["mcp", "resources", "read", uri, "--json"]) == 0
        envelope = json.loads(capsys.readouterr().out)
        read[uri.rsplit("/", 1)[-1]] = envelope
        assert envelope["schema_version"] == "mcp_resource_envelope.v1"
        assert envelope["denial_status"] == "allowed"
        assert envelope["metadata"]["orchestration_id"] == "mcp-core"
        assert str(tmp_path) not in json.dumps(envelope)

    assert read["manifest"]["resource_type"] == "orchestration_manifest"
    assert read["manifest"]["source_schema_version"] == "orchestration_manifest.v1"
    assert read["manifest"]["content"]["orchestration_id"] == "mcp-core"

    assert read["events"]["resource_type"] == "orchestration_events"
    assert read["events"]["source_schema_version"] == "orchestration_event.v1"
    assert read["events"]["content"]["schema_version"] == "mcp_orchestration_events.v1"
    assert read["events"]["content"]["orchestration_id"] == "mcp-core"
    assert read["events"]["content"]["count"] == summary["events_count"]
    assert any(event["type"] == "handoff_created" for event in read["events"]["content"]["events"])

    assert read["children"]["resource_type"] == "orchestration_children"
    assert read["children"]["content"] == {
        "schema_version": "mcp_orchestration_children.v1",
        "orchestration_id": "mcp-core",
        "children": summary["children"],
        "count": 2,
    }

    assert read["handoffs"]["resource_type"] == "orchestration_handoffs"
    assert read["handoffs"]["content"]["schema_version"] == "mcp_orchestration_handoffs.v1"
    assert read["handoffs"]["content"]["orchestration_id"] == "mcp-core"
    assert read["handoffs"]["content"]["count"] == 1
    assert read["handoffs"]["content"]["handoffs"][0]["from_child_id"] == "planner"

    records = [
        json.loads(line)
        for line in (tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {record["orchestration_id"] for record in records} == {"mcp-core"}
    assert {record["artifact_type"] for record in records} == {
        "orchestration_manifest",
        "orchestration_events",
        "orchestration_children",
        "orchestration_handoffs",
    }
    assert all(record["redaction_applied"] is False for record in records)
    assert all(record["denial_reason"] is None for record in records)
    assert "MCP core orchestration" not in json.dumps(records)


def test_orchestration_dependency_handoff_enters_downstream_context(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T09:00:00Z")
    seed_project(tmp_path)
    (tmp_path / "sample.py").write_text(
        "def identity(value):\n    return value\n", encoding="utf-8"
    )
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "handoff-flow",
                "title": "Planner to reviewer handoff",
                "children": [
                    {
                        "child_id": "reviewer",
                        "role": "reviewer",
                        "title": "Review plan",
                        "intent": "Review the generated planner handoff.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                        "depends_on": ["planner"],
                    },
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Plan work",
                        "intent": "Inspect the target and produce a safe handoff.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)

    assert [child["child_id"] for child in summary["children"]] == ["planner", "reviewer"]
    planner, reviewer = summary["children"]
    assert reviewer["depends_on"] == ["planner"]
    assert reviewer["handoffs"] == [
        {
            "handoff_id": "handoff-flow-planner-to-reviewer",
            "from_child_id": "planner",
            "from_run_id": planner["run_id"],
            "artifact": (
                ".agent-harness/orchestrations/handoff-flow/handoffs/planner-to-reviewer.json"
            ),
        }
    ]

    reviewer_manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / reviewer["run_id"] / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )
    handoff_items = [
        item
        for item in reviewer_manifest["items"]
        if item["source_kind"] == "orchestration_handoff"
    ]
    assert len(handoff_items) == 1
    handoff_item = handoff_items[0]
    assert handoff_item["sensitivity"] == "generated"
    assert handoff_item["orchestration_id"] == "handoff-flow"
    assert handoff_item["upstream_child_id"] == "planner"
    assert handoff_item["upstream_run_id"] == planner["run_id"]
    assert handoff_item["policy_decision_id"]

    handoff_path = tmp_path / summary["artifacts"]["handoff_planner_to_reviewer"]
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["schema_version"] == "orchestration_handoff.v1"
    assert handoff["sensitivity"] == "generated"
    assert handoff["policy_decision_id"] == handoff_item["policy_decision_id"]
    assert "provider" not in json.dumps(handoff).lower()

    assert main(["orchestration", "inspect", "handoff-flow"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    event_types = [event["type"] for event in inspected["events"]]
    assert event_types.index("child_finished") < event_types.index("handoff_created")
    assert inspected["handoffs"] == [handoff]
    assert inspected["artifact_index"]["artifacts"]["handoff_planner_to_reviewer"].endswith(
        "handoffs/planner-to-reviewer.json"
    )


def test_orchestration_dependency_cycle_is_spec_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "cycle-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "cycle",
                "title": "Invalid cycle",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Plan",
                        "intent": "Plan.",
                        "allowed_tools": ["read_file"],
                        "depends_on": ["reviewer"],
                    },
                    {
                        "child_id": "reviewer",
                        "role": "reviewer",
                        "title": "Review",
                        "intent": "Review.",
                        "allowed_tools": ["read_file"],
                        "depends_on": ["planner"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 2
    captured = capsys.readouterr()
    assert "dependency cycle" in captured.err
    assert "planner" in captured.err
    assert "reviewer" in captured.err
    assert not (tmp_path / ".agent-harness" / "orchestrations").exists()


def test_orchestration_risky_implementer_plan_pauses_before_child_and_resumes(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v11-phase4-implementer")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T10:00:00Z")
    seed_project(tmp_path)
    original = "def add_numbers(a, b):\n    return a + b\n"
    (tmp_path / "sample.py").write_text(original, encoding="utf-8")
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "risky-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "risky-implementer",
                "title": "Risky implementer plan",
                "children": [
                    {
                        "child_id": "implementer",
                        "role": "implementer",
                        "title": "Refactor implementation",
                        "intent": "Refactor add_numbers without bypassing approvals.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file", "patch_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    paused = json.loads(capsys.readouterr().out)

    assert paused["status"] == "paused"
    assert paused["approvals"] == ["action-risky-implementer-orchestration-plan"]
    assert paused["children"] == []
    assert not (tmp_path / ".agent-harness" / "runs").exists()
    plan = json.loads((tmp_path / paused["artifacts"]["orchestration_plan"]).read_text())
    assert plan["risk_summary"]["write_capable_children"] == ["implementer"]
    assert plan["children"][0]["effective_tools"] == ["read_file", "patch_file"]

    assert (
        main(
            [
                "orchestration",
                "approve",
                "risky-implementer",
                paused["approvals"][0],
                "--decision",
                "approve",
                "--actor",
                "reviewer",
                "--reason",
                "approved dry-run plan",
            ]
        )
        == 0
    )
    approval = json.loads(capsys.readouterr().out)
    assert approval["status"] == "approved"
    assert approval["tool_name"] == "orchestration_plan"

    assert main(["orchestration", "resume", "risky-implementer"]) == 0
    resumed = json.loads(capsys.readouterr().out)

    assert resumed["status"] == "dry_run"
    assert resumed["children"][0]["child_id"] == "implementer"
    assert resumed["children"][0]["status"] == "dry_run"
    assert resumed["children"][0]["run_id"] == "run-v11-phase4-implementer"
    child_summary = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / "run-v11-phase4-implementer" / "summary.json"
        ).read_text(encoding="utf-8")
    )
    assert child_summary["status"] == "dry_run"
    assert len(child_summary["approvals"]) == 1
    child_approval = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-v11-phase4-implementer"
            / "approvals"
            / f"{child_summary['approvals'][0]}.json"
        ).read_text(encoding="utf-8")
    )
    assert child_approval["tool_name"] == "patch_file"
    assert (tmp_path / "sample.py").read_text(encoding="utf-8") == original


def test_orchestration_role_ceiling_denies_planner_patch_before_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    (tmp_path / "sample.py").write_text(
        "def add_numbers(a, b):\n    return a + b\n", encoding="utf-8"
    )
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "planner-patch-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "planner-patch-denied",
                "title": "Planner patch denied",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Invalid planner patch",
                        "intent": "Refactor add_numbers.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file", "patch_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert "role ceiling" in captured.err
    assert "patch_file" in captured.err
    assert not (tmp_path / ".agent-harness" / "orchestrations").exists()
    assert not (tmp_path / ".agent-harness" / "runs").exists()


def test_orchestration_resume_rejects_tampered_plan_binding(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    (tmp_path / "sample.py").write_text(
        "def add_numbers(a, b):\n    return a + b\n", encoding="utf-8"
    )
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2), encoding="utf-8"
    )
    spec_path = tmp_path / "tamper-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "tamper-plan",
                "title": "Tamper plan",
                "children": [
                    {
                        "child_id": "implementer",
                        "role": "implementer",
                        "title": "Refactor implementation",
                        "intent": "Refactor add_numbers.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file", "patch_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    paused = json.loads(capsys.readouterr().out)
    action_id = paused["approvals"][0]
    assert (
        main(
            [
                "orchestration",
                "approve",
                "tamper-plan",
                action_id,
                "--decision",
                "approve",
            ]
        )
        == 0
    )
    capsys.readouterr()
    plan_path = tmp_path / paused["artifacts"]["orchestration_plan"]
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["children"][0]["effective_tools"] = ["read_file"]
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    assert main(["orchestration", "resume", "tamper-plan"]) == 1
    captured = capsys.readouterr()
    assert "binding drift" in captured.err
    assert not (tmp_path / ".agent-harness" / "runs").exists()


def test_orchestration_child_without_provider_profile_does_not_inherit_project_default(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v11-phase5-no-provider")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T11:00:00Z")
    _write_provider_config(
        tmp_path,
        [_mock_provider_profile()],
        default_provider_profile="mock-default",
    )
    _write_orchestration_policy(tmp_path)
    _write_sample_py(tmp_path)
    spec_path = tmp_path / "default-provider-not-inherited.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "default-provider-not-inherited",
                "title": "Default provider is not inherited",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Inspect target",
                        "intent": "Inspect the target without provider use.",
                        "target_paths": ["sample.py"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)

    child = summary["children"][0]
    assert child["status"] == "dry_run"
    child_run_dir = tmp_path / ".agent-harness" / "runs" / child["run_id"]
    assert not (child_run_dir / "provider.json").exists()
    assert not (child_run_dir / "provider_input.json").exists()
    assert not (child_run_dir / "provider_calls.json").exists()
    materialized_task = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "orchestrations"
            / "default-provider-not-inherited"
            / "children"
            / "planner.task.json"
        ).read_text(encoding="utf-8")
    )
    assert materialized_task["provider_profile"] is None


def test_orchestration_provider_child_pause_stops_downstream_children(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T11:30:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.setenv("AGENT_HARNESS_API_KEY", "phase5-provider-secret")
    _write_provider_config(tmp_path, [_local_endpoint_provider_profile()])
    _write_orchestration_policy(tmp_path, classify_sample=True)
    _write_sample_py(tmp_path)
    spec_path = _write_provider_dependency_spec(
        tmp_path,
        orchestration_id="provider-pause",
        filename="provider-pause.json",
        title="Provider pause",
        reviewer_intent="Review only after provider approval.",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    paused_for_plan = json.loads(capsys.readouterr().out)
    assert paused_for_plan["status"] == "paused"
    assert paused_for_plan["children"] == []
    action_id = paused_for_plan["approvals"][0]
    _approve_orchestration_plan(capsys, "provider-pause", action_id)

    assert main(["orchestration", "resume", "provider-pause"]) == 0
    paused_for_child = json.loads(capsys.readouterr().out)

    assert paused_for_child["status"] == "paused"
    assert paused_for_child["blocked_child_id"] == "provider"
    assert [child["child_id"] for child in paused_for_child["children"]] == ["provider"]
    provider_child = paused_for_child["children"][0]
    assert provider_child["status"] == "paused"
    assert provider_child["approvals"]
    assert not (
        tmp_path
        / ".agent-harness"
        / "orchestrations"
        / "provider-pause"
        / "children"
        / "reviewer.task.json"
    ).exists()
    provider_run_dir = tmp_path / ".agent-harness" / "runs" / provider_child["run_id"]
    assert (provider_run_dir / "provider.json").exists()
    assert (provider_run_dir / "provider_input.json").exists()
    assert (provider_run_dir / "provider_calls.json").exists()

    assert main(["orchestration", "inspect", "provider-pause"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["summary"]["blocked_child_id"] == "provider"
    assert inspected["events"][-1]["payload"]["status"] == "paused"
    assert "phase5-provider-secret" not in json.dumps(inspected)


def test_orchestration_resume_after_child_approval_skips_completed_children(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T12:00:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.setenv("AGENT_HARNESS_API_KEY", "phase5-resume-secret")
    _write_provider_config(tmp_path, [_local_endpoint_provider_profile()])
    _write_orchestration_policy(tmp_path, classify_sample=True)
    _write_sample_py(tmp_path)
    spec_path = _write_provider_dependency_spec(
        tmp_path,
        orchestration_id="provider-resume",
        filename="provider-resume.json",
        title="Provider resume",
        reviewer_intent="Review only after provider approval.",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    paused_for_plan = json.loads(capsys.readouterr().out)
    _approve_orchestration_plan(capsys, "provider-resume", paused_for_plan["approvals"][0])
    assert main(["orchestration", "resume", "provider-resume"]) == 0
    paused_for_child = json.loads(capsys.readouterr().out)
    provider_child = paused_for_child["children"][0]
    provider_run_id = provider_child["run_id"]
    child_approval = provider_child["approvals"][0]

    assert main(["approve", provider_run_id, child_approval, "--decision", "approve"]) == 0
    capsys.readouterr()

    assert main(["orchestration", "resume", "provider-resume"]) == 0
    resumed = json.loads(capsys.readouterr().out)

    assert resumed["status"] == "dry_run"
    assert resumed["blocked_child_id"] is None
    assert [child["child_id"] for child in resumed["children"]] == ["provider", "reviewer"]
    assert resumed["children"][0]["run_id"] == provider_run_id
    assert resumed["children"][0]["status"] == "dry_run"
    assert resumed["children"][1]["status"] == "dry_run"
    assert main(["orchestration", "inspect", "provider-resume"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    provider_starts = [
        event
        for event in inspected["events"]
        if event["type"] == "child_started" and event["payload"]["child_id"] == "provider"
    ]
    assert len(provider_starts) == 1
    assert "phase5-resume-secret" not in json.dumps(inspected)


def test_orchestration_child_failure_stops_downstream_children(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T12:30:00Z")
    monkeypatch.setenv("AGENT_HARNESS_LOCAL_ENDPOINT", "recorded://openai_compatible/read_only")
    monkeypatch.delenv("AGENT_HARNESS_API_KEY", raising=False)
    _write_provider_config(tmp_path, [_local_endpoint_provider_profile()])
    _write_orchestration_policy(tmp_path, classify_sample=True)
    _write_sample_py(tmp_path)
    spec_path = _write_provider_dependency_spec(
        tmp_path,
        orchestration_id="provider-failure",
        filename="provider-failure.json",
        title="Provider failure",
        reviewer_intent="Review only after provider succeeds.",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 0
    paused_for_plan = json.loads(capsys.readouterr().out)
    _approve_orchestration_plan(capsys, "provider-failure", paused_for_plan["approvals"][0])

    assert main(["orchestration", "resume", "provider-failure"]) == 0
    failed = json.loads(capsys.readouterr().out)

    assert failed["status"] == "failed"
    assert failed["blocked_child_id"] == "provider"
    assert [child["child_id"] for child in failed["children"]] == ["provider"]
    assert failed["children"][0]["status"] == "failed"
    assert not (
        tmp_path
        / ".agent-harness"
        / "orchestrations"
        / "provider-failure"
        / "children"
        / "reviewer.task.json"
    ).exists()
    assert main(["orchestration", "inspect", "provider-failure"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    event_types = [event["type"] for event in inspected["events"]]
    child_events = [
        json.loads(line)
        for line in (
            tmp_path / ".agent-harness" / "runs" / failed["children"][0]["run_id"] / "events.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert "provider_profile_invalid" in [event["type"] for event in child_events]
    assert "orchestration_failed" in event_types
