from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agent_harness.benchmarks.schema import (
    BenchmarkComparisonMetric,
    BenchmarkComparisonModeId,
    BenchmarkComparisonModeResult,
    BenchmarkComparisonRole,
    BenchmarkComparisonRoleRecommendation,
)

ROLE_ORDER: tuple[BenchmarkComparisonRole, ...] = (
    "planner",
    "implementer",
    "reviewer",
    "tester",
)
ROLE_MODE: dict[BenchmarkComparisonRole, BenchmarkComparisonModeId] = {
    "planner": "planner_implementer",
    "implementer": "planner_implementer",
    "reviewer": "planner_implementer_reviewer",
    "tester": "planner_implementer_reviewer_tester",
}
PREVIOUS_MODE: dict[BenchmarkComparisonModeId, BenchmarkComparisonModeId] = {
    "planner_implementer": "single_agent_baseline",
    "planner_implementer_reviewer": "planner_implementer",
    "planner_implementer_reviewer_tester": "planner_implementer_reviewer",
}
CORE_SUPPORTING_METRICS = [
    "task_success",
    "tests_passed",
    "policy_violations",
    "coordination_overhead_ratio",
    "defects_caught",
    "artifact_completeness",
]


def recommend_roles(
    modes: Sequence[BenchmarkComparisonModeResult],
) -> list[BenchmarkComparisonRoleRecommendation]:
    eligible_modes = {mode.mode_id: mode for mode in modes if mode.eligible}
    recommendations: list[BenchmarkComparisonRoleRecommendation] = []
    for role in ROLE_ORDER:
        mode_id = ROLE_MODE[role]
        current = eligible_modes.get(mode_id)
        previous = eligible_modes.get(PREVIOUS_MODE[mode_id])
        if current is None or previous is None:
            recommendations.append(
                BenchmarkComparisonRoleRecommendation(
                    role=role,
                    recommendation="neutral",
                    reason_codes=["mode_not_eligible"],
                    supporting_metric_names=[],
                    compared_mode_id=mode_id,
                    baseline_mode_id=PREVIOUS_MODE[mode_id],
                )
            )
            continue
        if role in {"planner", "implementer"}:
            recommendations.append(
                BenchmarkComparisonRoleRecommendation(
                    role=role,
                    recommendation="neutral",
                    reason_codes=["combined_mode_cannot_isolate_role"],
                    supporting_metric_names=CORE_SUPPORTING_METRICS,
                    compared_mode_id=current.mode_id,
                    baseline_mode_id=previous.mode_id,
                )
            )
            continue
        recommendations.append(_role_recommendation(role, current, previous))
    return recommendations


def _role_recommendation(
    role: BenchmarkComparisonRole,
    current: BenchmarkComparisonModeResult,
    previous: BenchmarkComparisonModeResult,
) -> BenchmarkComparisonRoleRecommendation:
    reason_codes = _gain_reason_codes(role, current, previous)
    policy_worsened = _metric_number(current, "policy_violations") > _metric_number(
        previous,
        "policy_violations",
    )
    overhead_added = _metric_number(current, "coordination_overhead_ratio") > _metric_number(
        previous,
        "coordination_overhead_ratio",
    )
    details = {
        "current_mode_id": current.mode_id,
        "previous_mode_id": previous.mode_id,
        "policy_violations_worsened": policy_worsened,
        "coordination_overhead_delta": round(
            _metric_number(current, "coordination_overhead_ratio")
            - _metric_number(previous, "coordination_overhead_ratio"),
            4,
        ),
    }
    if policy_worsened:
        return BenchmarkComparisonRoleRecommendation(
            role=role,
            recommendation="remove_candidate",
            reason_codes=[*reason_codes, "policy_violations_worsened"],
            supporting_metric_names=CORE_SUPPORTING_METRICS,
            compared_mode_id=current.mode_id,
            baseline_mode_id=previous.mode_id,
            details=details,
        )
    if reason_codes and not policy_worsened:
        return BenchmarkComparisonRoleRecommendation(
            role=role,
            recommendation="retain",
            reason_codes=reason_codes,
            supporting_metric_names=CORE_SUPPORTING_METRICS,
            compared_mode_id=current.mode_id,
            baseline_mode_id=previous.mode_id,
            details=details,
        )
    if overhead_added and not reason_codes:
        return BenchmarkComparisonRoleRecommendation(
            role=role,
            recommendation="remove_candidate",
            reason_codes=["added_overhead_without_measurable_gain"],
            supporting_metric_names=CORE_SUPPORTING_METRICS,
            compared_mode_id=current.mode_id,
            baseline_mode_id=previous.mode_id,
            details=details,
        )
    if not reason_codes:
        reason_codes = ["no_measurable_role_delta"]
    return BenchmarkComparisonRoleRecommendation(
        role=role,
        recommendation="neutral",
        reason_codes=reason_codes,
        supporting_metric_names=CORE_SUPPORTING_METRICS,
        compared_mode_id=current.mode_id,
        baseline_mode_id=previous.mode_id,
        details=details,
    )


def _gain_reason_codes(
    role: BenchmarkComparisonRole,
    current: BenchmarkComparisonModeResult,
    previous: BenchmarkComparisonModeResult,
) -> list[str]:
    reasons: list[str] = []
    if _role_defects(current, role) > _role_defects(previous, role):
        reasons.append("defect_caught_by_role")
    if _metric_bool_gain(current, previous, "task_success"):
        reasons.append("task_success_improved")
    if _metric_bool_gain(current, previous, "tests_passed"):
        reasons.append("tests_passed_improved")
    if _metric_number(current, "policy_violations") < _metric_number(
        previous,
        "policy_violations",
    ):
        reasons.append("policy_violations_reduced")
    if _metric_bool_gain(current, previous, "artifact_completeness"):
        reasons.append("artifact_completeness_improved")
    if _metric_bool_gain(current, previous, "failure_attribution_clarity"):
        reasons.append("failure_attribution_improved")
    return reasons


def _metrics(mode: BenchmarkComparisonModeResult) -> dict[str, BenchmarkComparisonMetric]:
    return {metric.name: metric for metric in mode.metrics}


def _metric_value(mode: BenchmarkComparisonModeResult, name: str) -> Any:
    metric = _metrics(mode).get(name)
    return None if metric is None else metric.value


def _metric_number(mode: BenchmarkComparisonModeResult, name: str) -> float:
    value = _metric_value(mode, name)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _metric_bool_gain(
    current: BenchmarkComparisonModeResult,
    previous: BenchmarkComparisonModeResult,
    name: str,
) -> bool:
    return _metric_value(current, name) is True and _metric_value(previous, name) is not True


def _role_defects(mode: BenchmarkComparisonModeResult, role: BenchmarkComparisonRole) -> int:
    metric = _metrics(mode).get("defects_caught")
    if metric is None:
        return 0
    value = metric.details.get(role)
    return value if isinstance(value, int) else 0
