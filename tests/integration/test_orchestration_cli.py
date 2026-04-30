from __future__ import annotations

import copy
import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from tests.conftest import seed_project


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
