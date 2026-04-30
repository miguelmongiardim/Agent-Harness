from __future__ import annotations

from typing import Any

from agent_harness.benchmarks.interpretation import recommend_roles
from agent_harness.benchmarks.schema import (
    BenchmarkComparisonMetric,
    BenchmarkComparisonModeId,
    BenchmarkComparisonModeResult,
)


def test_role_recommendations_flag_overhead_without_gain_and_retain_defect_catches() -> None:
    recommendations = recommend_roles(
        [
            _mode(
                "single_agent_baseline",
                child_run_count=1,
                overhead=0.0,
                defects={"reviewer": 0, "tester": 0},
            ),
            _mode(
                "planner_implementer",
                child_run_count=2,
                overhead=1.0,
                defects={"reviewer": 0, "tester": 0},
            ),
            _mode(
                "planner_implementer_reviewer",
                child_run_count=3,
                overhead=2.0,
                defects={"reviewer": 0, "tester": 0},
            ),
            _mode(
                "planner_implementer_reviewer_tester",
                child_run_count=4,
                overhead=2.5,
                defects={"reviewer": 0, "tester": 1},
            ),
        ]
    )

    by_role = {recommendation.role: recommendation for recommendation in recommendations}

    assert by_role["reviewer"].recommendation == "remove_candidate"
    assert "added_overhead_without_measurable_gain" in by_role["reviewer"].reason_codes
    assert "coordination_overhead_ratio" in by_role["reviewer"].supporting_metric_names
    assert "defects_caught" in by_role["reviewer"].supporting_metric_names

    assert by_role["tester"].recommendation == "retain"
    assert "defect_caught_by_role" in by_role["tester"].reason_codes
    assert "defects_caught" in by_role["tester"].supporting_metric_names
    assert by_role["tester"].default_recommendation == "not_recommended"


def _mode(
    mode_id: BenchmarkComparisonModeId,
    *,
    child_run_count: int,
    overhead: float,
    defects: dict[str, int],
    policy_violations: int = 0,
) -> BenchmarkComparisonModeResult:
    return BenchmarkComparisonModeResult(
        mode_id=mode_id,
        label=mode_id.replace("_", " "),
        execution_order=child_run_count,
        status="completed" if mode_id == "single_agent_baseline" else "dry_run",
        passed=True,
        child_run_count=child_run_count,
        tool_call_count=1,
        handoff_count=max(0, child_run_count - 1),
        artifact_completeness={"synthetic": True},
        metrics=[
            _metric("task_success", True),
            _metric("tests_passed", None, status="not_applicable"),
            _metric("policy_violations", policy_violations),
            _metric("coordination_overhead_ratio", overhead),
            _metric("defects_caught", sum(defects.values()), details=defects),
            _metric("artifact_completeness", True),
        ],
    )


def _metric(
    name: str,
    value: Any,
    *,
    status: str = "available",
    details: dict[str, Any] | None = None,
) -> BenchmarkComparisonMetric:
    return BenchmarkComparisonMetric(
        name=name,
        status=status,  # type: ignore[arg-type]
        value=value,
        details=details or {},
    )
