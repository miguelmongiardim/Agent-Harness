from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project

REQUIRED_PHASE3_METRICS = {
    "task_success",
    "tests_passed",
    "policy_violations",
    "approval_correctness",
    "child_run_count",
    "tool_call_count",
    "handoff_count",
    "handoff_size_bytes",
    "coordination_overhead_ratio",
    "defects_caught",
    "failure_attribution_clarity",
    "artifact_completeness",
    "token_usage",
    "runtime_seconds",
    "cost_usd",
}


def test_benchmark_compare_single_case_writes_baseline_first_comparison_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T15:00:00Z")
    seed_project(tmp_path)

    assert main(["benchmark", "compare", "local-samples", "terminal-readonly-inspect"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "benchmark_comparison_result.v1"
    assert result["pack_id"] == "local-samples"
    assert result["case_id"] == "terminal-readonly-inspect"
    assert result["baseline_mode_id"] == "single_agent_baseline"
    assert [mode["mode_id"] for mode in result["modes"]] == [
        "single_agent_baseline",
        "planner_implementer",
        "planner_implementer_reviewer",
        "planner_implementer_reviewer_tester",
    ]

    baseline = result["modes"][0]
    assert baseline["execution_order"] == 1
    assert baseline["status"] == "completed"
    assert baseline["passed"] is True
    assert baseline["run_id"]
    assert baseline["run_export"].endswith("-run.json")
    assert baseline["benchmark_result"].endswith(".json")
    assert baseline["orchestration_id"] is None
    assert baseline["artifact_completeness"] == {
        "benchmark_result": True,
        "run_export": True,
    }

    planner_implementer = result["modes"][1]
    assert planner_implementer["execution_order"] == 2
    assert planner_implementer["status"] == "dry_run"
    assert planner_implementer["passed"] is True
    assert (
        planner_implementer["orchestration_id"]
        == "cmp-local-samples-terminal-readonly-inspect-planner-implementer"
    )
    assert planner_implementer["orchestration_export"].endswith(".orchestration.json")
    assert planner_implementer["orchestration_summary"].endswith("summary.json")
    assert [child["child_id"] for child in planner_implementer["child_runs"]] == [
        "planner",
        "implementer",
    ]
    assert planner_implementer["child_run_count"] == 2
    assert planner_implementer["handoff_count"] == 1
    assert planner_implementer["tool_call_count"] >= 2
    assert planner_implementer["artifact_completeness"] == {
        "orchestration_export": True,
        "orchestration_summary": True,
        "child_run_summaries": True,
    }

    artifact_path = tmp_path / result["result_artifact"]
    assert artifact_path.exists()
    assert json.loads(artifact_path.read_text(encoding="utf-8")) == result
    assert (tmp_path / baseline["run_export"]).exists()
    assert (tmp_path / planner_implementer["orchestration_export"]).exists()
    for child in planner_implementer["child_runs"]:
        assert (tmp_path / child["run_summary_artifact"]).exists()

    serialized = json.dumps(result)
    assert str(tmp_path) not in serialized
    assert "raw_request" not in serialized
    assert "raw_response" not in serialized


def test_benchmark_compare_generates_sequential_modes_and_tester_eligibility(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T15:30:00Z")
    seed_project(tmp_path)

    assert main(["benchmark", "compare", "local-samples", "terminal-readonly-inspect"]) == 0
    no_test_result = json.loads(capsys.readouterr().out)

    assert [mode["mode_id"] for mode in no_test_result["modes"]] == [
        "single_agent_baseline",
        "planner_implementer",
        "planner_implementer_reviewer",
        "planner_implementer_reviewer_tester",
    ]
    no_test_modes = {mode["mode_id"]: mode for mode in no_test_result["modes"]}
    reviewer = no_test_modes["planner_implementer_reviewer"]
    assert reviewer["eligible"] is True
    assert reviewer["skip_reason"] is None
    assert reviewer["status"] == "dry_run"
    assert [child["child_id"] for child in reviewer["child_runs"]] == [
        "planner",
        "implementer",
        "reviewer",
    ]
    assert reviewer["handoff_count"] == 2
    reviewer_export = json.loads(
        (tmp_path / reviewer["orchestration_export"]).read_text(encoding="utf-8")
    )
    assert {
        (handoff["from_child_id"], handoff["to_child_id"])
        for handoff in reviewer_export["handoffs"]
    } == {("planner", "implementer"), ("implementer", "reviewer")}

    skipped_tester = no_test_modes["planner_implementer_reviewer_tester"]
    assert skipped_tester["eligible"] is False
    assert skipped_tester["status"] == "skipped"
    assert skipped_tester["passed"] is False
    assert skipped_tester["skip_reason"] == "tester mode requires executable test_commands"
    assert skipped_tester["child_runs"] == []
    assert skipped_tester["orchestration_export"] is None

    assert main(["benchmark", "compare", "local-samples", "terminal-test-runner"]) == 0
    test_enabled_result = json.loads(capsys.readouterr().out)
    test_enabled_modes = {mode["mode_id"]: mode for mode in test_enabled_result["modes"]}
    tester = test_enabled_modes["planner_implementer_reviewer_tester"]

    assert tester["eligible"] is True
    assert tester["skip_reason"] is None
    assert tester["status"] == "dry_run"
    assert [child["child_id"] for child in tester["child_runs"]] == [
        "planner",
        "implementer",
        "reviewer",
        "tester",
    ]
    assert tester["handoff_count"] == 3
    tester_export_path = tmp_path / tester["orchestration_export"]
    tester_export = json.loads(tester_export_path.read_text(encoding="utf-8"))
    assert {
        (handoff["from_child_id"], handoff["to_child_id"]) for handoff in tester_export["handoffs"]
    } == {
        ("planner", "implementer"),
        ("implementer", "reviewer"),
        ("reviewer", "tester"),
    }
    tester_task_path = next(
        child["materialized_task_path"]
        for child in tester_export["child_artifacts"]
        if child["child_id"] == "tester"
    )
    comparison_workspace = tester_export_path.parents[2]
    tester_task = json.loads(
        (comparison_workspace / tester_task_path).read_text(encoding="utf-8")
    )
    assert tester_task["allowed_tools"] == ["read_file", "run_tests"]
    assert tester_task["test_commands"] == [["python", "-m", "pytest", "tests"]]


def test_benchmark_compare_carries_context_queries_to_generated_children(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T16:00:00Z")
    monkeypatch.setattr(
        "agent_harness.core.runtime.optional_dense_dependencies_available",
        lambda: True,
    )
    seed_project(tmp_path)

    assert main(["benchmark", "compare", "local-samples", "swebench-dense-retrieval"]) == 0
    result = json.loads(capsys.readouterr().out)
    mode = next(
        mode for mode in result["modes"] if mode["mode_id"] == "planner_implementer"
    )
    export_path = tmp_path / mode["orchestration_export"]
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    comparison_workspace = export_path.parents[2]
    materialized_tasks = {
        child["child_id"]: json.loads(
            (comparison_workspace / child["materialized_task_path"]).read_text(
                encoding="utf-8"
            )
        )
        for child in exported["child_artifacts"]
    }

    assert materialized_tasks["planner"]["context_queries"] == ["semantic helper"]
    assert materialized_tasks["planner"]["allowed_tools"] == ["search_code"]
    assert materialized_tasks["implementer"]["context_queries"] == ["semantic helper"]
    assert materialized_tasks["implementer"]["allowed_tools"] == ["search_code"]


def test_benchmark_compare_records_required_metrics_from_linked_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T16:30:00Z")
    seed_project(tmp_path)

    assert main(["benchmark", "compare", "local-samples", "terminal-test-runner"]) == 0
    result = json.loads(capsys.readouterr().out)

    policy_violation_values = []
    for mode in result["modes"]:
        if not mode["eligible"]:
            continue
        metrics = {metric["name"]: metric for metric in mode["metrics"]}
        assert set(metrics) == REQUIRED_PHASE3_METRICS
        assert metrics["task_success"]["status"] == "available"
        assert metrics["task_success"]["value"] == mode["passed"]
        assert metrics["child_run_count"]["value"] == mode["child_run_count"]
        assert metrics["tool_call_count"]["value"] == mode["tool_call_count"]
        assert metrics["handoff_count"]["value"] == mode["handoff_count"]
        policy_details = metrics["policy_violations"]["details"]
        policy_violation_values.append(metrics["policy_violations"]["value"])
        assert metrics["policy_violations"]["value"] == (
            policy_details["denied_policy_decisions"]
            + policy_details["denied_tool_observations"]
            + policy_details["authority_failures"]
        )
        assert metrics["approval_correctness"]["details"] == {
            "pending": 0,
            "approved": 0,
            "denied": 0,
            "binding_drift": 0,
        }
        assert metrics["artifact_completeness"]["status"] == "available"
        assert metrics["artifact_completeness"]["details"]["missing"] == []
        assert metrics["token_usage"]["status"] == "unavailable"
        assert metrics["runtime_seconds"]["status"] == "unavailable"
        assert metrics["cost_usd"]["status"] == "unavailable"

    assert max(policy_violation_values) > 0

    baseline = next(mode for mode in result["modes"] if mode["mode_id"] == "single_agent_baseline")
    baseline_metrics = {metric["name"]: metric for metric in baseline["metrics"]}
    assert baseline_metrics["tests_passed"]["status"] == "available"
    assert baseline_metrics["tests_passed"]["value"] is False
    assert baseline_metrics["tests_passed"]["reason"] == "no successful run_tests evidence"

    tester = next(
        mode
        for mode in result["modes"]
        if mode["mode_id"] == "planner_implementer_reviewer_tester"
    )
    tester_metrics = {metric["name"]: metric for metric in tester["metrics"]}
    assert tester_metrics["tests_passed"]["status"] == "available"
    assert tester_metrics["tests_passed"]["value"] is False
    assert tester_metrics["tests_passed"]["reason"] == "no successful run_tests evidence"
    assert tester_metrics["tests_passed"]["details"]["dry_run_skips"] == 0
    assert tester_metrics["handoff_size_bytes"]["value"] > 0
    assert tester_metrics["coordination_overhead_ratio"]["value"] > 0


def test_benchmark_compare_approval_metric_records_approved_baseline_actions(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-30T17:00:00Z")
    seed_project(tmp_path)

    assert main(["benchmark", "compare", "local-samples", "swebench-python-refactor"]) == 0
    result = json.loads(capsys.readouterr().out)
    baseline = next(mode for mode in result["modes"] if mode["mode_id"] == "single_agent_baseline")
    metrics = {metric["name"]: metric for metric in baseline["metrics"]}

    assert metrics["approval_correctness"]["status"] == "available"
    assert metrics["approval_correctness"]["value"] == "approved"
    assert metrics["approval_correctness"]["details"]["approved"] >= 1
    assert metrics["approval_correctness"]["details"]["pending"] == 0
    assert metrics["approval_correctness"]["details"]["denied"] == 0
    assert metrics["approval_correctness"]["details"]["binding_drift"] == 0
