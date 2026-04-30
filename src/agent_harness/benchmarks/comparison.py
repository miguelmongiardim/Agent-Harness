from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from agent_harness.benchmarks.packs import (
    _case_by_id,
    _prepare_benchmark_workspace,
    _project_relative,
    load_benchmark_pack,
    run_benchmark_case,
)
from agent_harness.benchmarks.schema import (
    BenchmarkCaseRecord,
    BenchmarkComparisonChildRun,
    BenchmarkComparisonMetric,
    BenchmarkComparisonModeId,
    BenchmarkComparisonModeResult,
    BenchmarkComparisonResult,
    BenchmarkPackRecord,
    BenchmarkResult,
)
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.orchestration import export_orchestration, run_orchestration
from agent_harness.tools.schema import ToolName
from agent_harness.utils import load_json, write_json

ROLE_TOOL_ORDER: list[ToolName] = [
    "read_file",
    "search_code",
    "run_tests",
    "patch_file",
    "git_status",
    "git_commit",
]
ROLE_TOOL_CEILINGS: dict[str, set[ToolName]] = {
    "planner": {"read_file", "search_code"},
    "implementer": {"read_file", "search_code", "patch_file"},
    "reviewer": {"read_file", "search_code", "git_status"},
    "tester": {"read_file", "search_code", "run_tests"},
}
ORCHESTRATION_MODE_DEFINITIONS: list[tuple[BenchmarkComparisonModeId, str, list[str], int]] = [
    ("planner_implementer", "Planner -> implementer", ["planner", "implementer"], 2),
    (
        "planner_implementer_reviewer",
        "Planner -> implementer -> reviewer",
        ["planner", "implementer", "reviewer"],
        3,
    ),
    (
        "planner_implementer_reviewer_tester",
        "Planner -> implementer -> reviewer -> tester",
        ["planner", "implementer", "reviewer", "tester"],
        4,
    ),
]
TESTER_SKIP_REASON = "tester mode requires executable test_commands"


def run_benchmark_comparison(
    project_root: Path,
    pack_id: str,
    case_id: str,
) -> BenchmarkComparisonResult:
    root = project_root.resolve()
    pack = load_benchmark_pack(pack_id)
    case = _case_by_id(pack, case_id)

    baseline = run_benchmark_case(root, pack_id, case_id)
    baseline_mode = _baseline_mode(root, case, baseline)
    orchestration_modes = _orchestration_modes(root, pack, case)

    result_path = (
        root
        / ".agent-harness"
        / "benchmarks"
        / "comparisons"
        / f"{pack.pack_id}-{case.case_id}.json"
    )
    result = BenchmarkComparisonResult(
        pack_id=pack.pack_id,
        version=pack.version,
        case_id=case.case_id,
        benchmark_kind=case.benchmark_kind,
        result_artifact=_project_relative(root, result_path),
        modes=[baseline_mode, *orchestration_modes],
    )
    write_json(result_path, result.model_dump(mode="json"))
    return result


def _baseline_mode(
    root: Path,
    case: BenchmarkCaseRecord,
    baseline: BenchmarkResult,
) -> BenchmarkComparisonModeResult:
    result_path = root / baseline.result_artifact
    export_path = root / baseline.run_export
    artifact_completeness = {
        "benchmark_result": result_path.exists(),
        "run_export": export_path.exists(),
    }
    if not baseline.passed:
        raise ValueError("baseline benchmark run did not pass")
    if not all(artifact_completeness.values()):
        raise ValueError("baseline benchmark evidence is incomplete")
    exported = _load_object(export_path)
    if exported.get("summary", {}).get("run_id") != baseline.run_id:
        raise ValueError("baseline run export cannot be inspected")
    events = _object_list(exported.get("events", []))
    tool_call_count = _tool_activity_count(events)
    return BenchmarkComparisonModeResult(
        mode_id="single_agent_baseline",
        label="Single-agent baseline",
        execution_order=1,
        status=baseline.status,
        passed=baseline.passed,
        run_id=baseline.run_id,
        benchmark_result=baseline.result_artifact,
        run_export=baseline.run_export,
        child_run_count=1,
        tool_call_count=tool_call_count,
        handoff_count=0,
        artifact_completeness=artifact_completeness,
        metrics=_mode_metrics(
            case=case,
            passed=baseline.passed,
            child_run_count=1,
            tool_call_count=tool_call_count,
            handoff_count=0,
            handoffs=[],
            artifact_completeness=artifact_completeness,
            run_events=events,
            orchestration_events=[],
            approvals=[],
        ),
    )


def _orchestration_modes(
    root: Path,
    pack: BenchmarkPackRecord,
    case: BenchmarkCaseRecord,
) -> list[BenchmarkComparisonModeResult]:
    modes: list[BenchmarkComparisonModeResult] = []
    for mode_id, label, roles, execution_order in ORCHESTRATION_MODE_DEFINITIONS:
        if "tester" in roles and not _case_has_executable_tests(case):
            modes.append(_skipped_mode(mode_id, label, execution_order, TESTER_SKIP_REASON))
            continue
        modes.append(_orchestration_mode(root, pack, case, mode_id, label, roles, execution_order))
    return modes


def _skipped_mode(
    mode_id: BenchmarkComparisonModeId,
    label: str,
    execution_order: int,
    reason: str,
) -> BenchmarkComparisonModeResult:
    return BenchmarkComparisonModeResult(
        mode_id=mode_id,
        label=label,
        execution_order=execution_order,
        status="skipped",
        passed=False,
        eligible=False,
        skip_reason=reason,
    )


def _orchestration_mode(
    root: Path,
    pack: BenchmarkPackRecord,
    case: BenchmarkCaseRecord,
    mode_id: BenchmarkComparisonModeId,
    label: str,
    roles: list[str],
    execution_order: int,
) -> BenchmarkComparisonModeResult:
    mode_slug = mode_id.replace("_", "-")
    workspace = _prepare_benchmark_workspace(
        root,
        pack,
        case,
        workspace=(
            root
            / ".agent-harness"
            / "benchmarks"
            / "comparison-workspaces"
            / pack.pack_id
            / case.case_id
            / mode_slug
        ),
        policy=_orchestration_policy(),
    )
    orchestration_id = f"cmp-{pack.pack_id}-{case.case_id}-{mode_slug}"
    spec_path = workspace / f"{mode_slug}.orchestration.json"
    write_json(spec_path, _mode_spec(orchestration_id, case, roles))

    summary = run_orchestration(workspace, spec_path, dry_run=True)
    export_path = export_orchestration(workspace, summary.orchestration_id)
    exported = _load_object(export_path)
    orchestration_events = _object_list(exported.get("events", []))
    handoffs = _object_list(exported.get("handoffs", []))
    approvals = _object_list(exported.get("approvals", []))
    summary_path = workspace / summary.artifacts["summary"]
    child_runs = [
        BenchmarkComparisonChildRun(
            child_id=child.child_id,
            role=child.role,
            run_id=child.run_id,
            status=child.status,
            run_summary_artifact=_project_relative(root, workspace / child.run_summary_artifact),
        )
        for child in summary.children
    ]
    artifact_completeness = {
        "orchestration_export": export_path.exists(),
        "orchestration_summary": summary_path.exists(),
        "child_run_summaries": all(
            (root / child.run_summary_artifact).exists() for child in child_runs
        ),
    }
    run_events = [
        event
        for child in summary.children
        for event in _run_events(workspace, child.run_id)
    ]
    tool_call_count = _tool_activity_count(run_events)
    handoff_count = len(handoffs)
    passed = summary.status in {"completed", "dry_run"} and all(artifact_completeness.values())
    return BenchmarkComparisonModeResult(
        mode_id=mode_id,
        label=label,
        execution_order=execution_order,
        status=summary.status,
        passed=passed,
        orchestration_id=summary.orchestration_id,
        orchestration_export=_project_relative(root, export_path),
        orchestration_summary=_project_relative(root, summary_path),
        child_runs=child_runs,
        child_run_count=len(child_runs),
        tool_call_count=tool_call_count,
        handoff_count=handoff_count,
        artifact_completeness=artifact_completeness,
        metrics=_mode_metrics(
            case=case,
            passed=passed,
            child_run_count=len(child_runs),
            tool_call_count=tool_call_count,
            handoff_count=handoff_count,
            handoffs=handoffs,
            artifact_completeness=artifact_completeness,
            run_events=run_events,
            orchestration_events=orchestration_events,
            approvals=approvals,
        ),
    )


def _mode_spec(
    orchestration_id: str,
    case: BenchmarkCaseRecord,
    roles: list[str],
) -> dict[str, Any]:
    target_paths = list(case.task.target_paths)
    context_queries = list(case.task.context_queries)
    children: list[dict[str, Any]] = []
    for index, role in enumerate(roles):
        child: dict[str, Any] = {
            "child_id": role,
            "role": role,
            "title": f"{_role_title(role)} {case.title}",
            "intent": _role_intent(role),
            "target_paths": target_paths,
            "context_queries": context_queries,
            "allowed_tools": _allowed_tools_for_role(case, role),
        }
        if index > 0:
            child["depends_on"] = [roles[index - 1]]
        if role == "tester":
            child["test_commands"] = [list(command) for command in case.task.test_commands]
        children.append(child)
    return {
        "schema_version": "orchestration.v1",
        "orchestration_id": orchestration_id,
        "title": f"Compare {case.case_id} {' '.join(roles)} mode",
        "children": children,
    }


def _allowed_tools_for_role(case: BenchmarkCaseRecord, role: str) -> list[ToolName]:
    declared = set(case.task.allowed_tools or ROLE_TOOL_ORDER)
    role_ceiling = ROLE_TOOL_CEILINGS[role]
    return [tool for tool in ROLE_TOOL_ORDER if tool in declared and tool in role_ceiling]


def _case_has_executable_tests(case: BenchmarkCaseRecord) -> bool:
    declared = set(case.task.allowed_tools or ROLE_TOOL_ORDER)
    return bool(case.task.test_commands) and "run_tests" in declared


def _role_title(role: str) -> str:
    return {
        "planner": "Plan",
        "implementer": "Implement",
        "reviewer": "Review",
        "tester": "Test",
    }[role]


def _role_intent(role: str) -> str:
    return {
        "planner": "Inspect the benchmark case and produce a dependency handoff.",
        "implementer": "Use the upstream handoff to inspect or implement the benchmark task.",
        "reviewer": "Review the upstream child evidence and benchmark task scope.",
        "tester": "Run only the executable test commands declared by the benchmark case.",
    }[role]


def _orchestration_policy() -> dict[str, Any]:
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    return policy


def _load_object(path: Path) -> dict[str, Any]:
    loaded = load_json(path)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path.name} did not contain an object")
    return loaded


def _mode_metrics(
    *,
    case: BenchmarkCaseRecord | None,
    passed: bool,
    child_run_count: int,
    tool_call_count: int,
    handoff_count: int,
    handoffs: list[dict[str, Any]],
    artifact_completeness: dict[str, bool],
    run_events: list[dict[str, Any]],
    orchestration_events: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> list[BenchmarkComparisonMetric]:
    missing_artifacts = [
        artifact for artifact, present in sorted(artifact_completeness.items()) if not present
    ]
    handoff_size_bytes = sum(
        len(str(handoff.get("summary", "")).encode("utf-8")) for handoff in handoffs
    )
    approval_details = _approval_correctness(run_events, orchestration_events, approvals)
    policy_violations = _policy_violation_details(run_events, orchestration_events)
    tests_passed = _tests_passed_metric(case, run_events)
    coordination_ratio = _coordination_overhead_ratio(
        child_run_count=child_run_count,
        tool_call_count=tool_call_count,
        handoff_count=handoff_count,
        orchestration_events=orchestration_events,
        approvals=approvals,
    )
    return [
        _metric("task_success", "available", passed),
        tests_passed,
        _metric(
            "policy_violations",
            "available",
            policy_violations["total"],
            details=policy_violations,
        ),
        _metric(
            "approval_correctness",
            "available",
            _approval_state(approval_details),
            details=approval_details,
        ),
        _metric("child_run_count", "available", child_run_count, unit="runs"),
        _metric("tool_call_count", "available", tool_call_count, unit="events"),
        _metric("handoff_count", "available", handoff_count, unit="handoffs"),
        _metric("handoff_size_bytes", "available", handoff_size_bytes, unit="bytes"),
        _metric("coordination_overhead_ratio", "available", coordination_ratio),
        _metric("defects_caught", "available", 0, details={"reviewer": 0, "tester": 0}),
        _failure_attribution_metric(passed, run_events, orchestration_events),
        _metric(
            "artifact_completeness",
            "available",
            not missing_artifacts,
            details={"missing": missing_artifacts, "artifacts": artifact_completeness},
        ),
        _metric(
            "token_usage",
            "unavailable",
            None,
            reason="token evidence is not exposed by linked run evidence",
        ),
        _metric(
            "runtime_seconds",
            "unavailable",
            None,
            reason="runtime evidence is not exposed by linked run evidence",
        ),
        _metric(
            "cost_usd",
            "unavailable",
            None,
            unit="usd",
            reason="cost evidence is not exposed by linked run evidence",
        ),
    ]


def _metric(
    name: str,
    status: str,
    value: Any = None,
    *,
    unit: str | None = None,
    reason: str | None = None,
    evidence: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> BenchmarkComparisonMetric:
    return BenchmarkComparisonMetric(
        name=name,
        status=status,  # type: ignore[arg-type]
        value=value,
        unit=unit,
        reason=reason,
        evidence=evidence or [],
        details=details or {},
    )


def _tests_passed_metric(
    case: BenchmarkCaseRecord | None,
    run_events: list[dict[str, Any]],
) -> BenchmarkComparisonMetric:
    declared_commands = [list(command) for command in case.task.test_commands] if case else []
    observations = _tool_observations(run_events, tool_name="run_tests")
    dry_run_skips = sum(1 for observation in observations if observation.get("status") == "dry_run")
    successful_commands = [
        observation.get("output", {}).get("command")
        for observation in observations
        if observation.get("success") is True and observation.get("status") == "ok"
    ]
    details = {
        "declared_commands": declared_commands,
        "successful_commands": successful_commands,
        "dry_run_skips": dry_run_skips,
    }
    if not declared_commands:
        return _metric(
            "tests_passed",
            "not_applicable",
            None,
            reason="no executable test_commands declared",
            details=details,
        )
    passed = all(command in successful_commands for command in declared_commands)
    reason = None
    if not passed:
        reason = (
            "no successful run_tests evidence"
            if not successful_commands
            else "missing successful run_tests evidence"
        )
    return _metric("tests_passed", "available", passed, reason=reason, details=details)


def _policy_violation_details(
    run_events: list[dict[str, Any]],
    orchestration_events: list[dict[str, Any]],
) -> dict[str, int]:
    denied_decisions = 0
    for event in [*run_events, *orchestration_events]:
        if event.get("type") != "policy_decision":
            continue
        decision = event.get("payload", {}).get("decision")
        if isinstance(decision, dict) and decision.get("allowed") is False:
            denied_decisions += 1
    denied_observations = sum(
        1
        for observation in _tool_observations(run_events)
        if observation.get("status") == "denied"
    )
    authority_failures = sum(
        1
        for event in orchestration_events
        if event.get("type") == "orchestration_failed"
        and "role ceiling" in json.dumps(event.get("payload", {})).lower()
    )
    total = denied_decisions + denied_observations + authority_failures
    return {
        "total": total,
        "denied_policy_decisions": denied_decisions,
        "denied_tool_observations": denied_observations,
        "authority_failures": authority_failures,
    }


def _approval_correctness(
    run_events: list[dict[str, Any]],
    orchestration_events: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> dict[str, int]:
    statuses: dict[str, str] = {}
    for approval in approvals:
        approval_id = approval.get("approval_id") or approval.get("action_id")
        status = approval.get("status")
        if isinstance(approval_id, str) and isinstance(status, str):
            statuses[approval_id] = status
    for event in [*run_events, *orchestration_events]:
        if event.get("type") not in {"approval_recorded", "approval_decided"}:
            continue
        approval = event.get("payload", {}).get("approval")
        if not isinstance(approval, dict):
            continue
        approval_id = approval.get("approval_id") or approval.get("action_id")
        status = approval.get("status")
        if isinstance(approval_id, str) and isinstance(status, str):
            statuses[approval_id] = status
    binding_drift = sum(
        1
        for event in [*run_events, *orchestration_events]
        if "binding drift" in json.dumps(event).lower()
    )
    return {
        "pending": sum(1 for status in statuses.values() if status == "pending"),
        "approved": sum(1 for status in statuses.values() if status == "approved"),
        "denied": sum(1 for status in statuses.values() if status == "denied"),
        "binding_drift": binding_drift,
    }


def _approval_state(details: dict[str, int]) -> str:
    if details["binding_drift"]:
        return "binding_drift"
    if details["denied"]:
        return "denied"
    if details["pending"]:
        return "pending"
    if details["approved"]:
        return "approved"
    return "none"


def _coordination_overhead_ratio(
    *,
    child_run_count: int,
    tool_call_count: int,
    handoff_count: int,
    orchestration_events: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> float:
    if not orchestration_events:
        return 0.0
    overhead_units = (
        len(orchestration_events)
        + max(0, child_run_count - 1)
        + len(approvals)
        + handoff_count
    )
    return round(overhead_units / max(1, tool_call_count), 4)


def _failure_attribution_metric(
    passed: bool,
    run_events: list[dict[str, Any]],
    orchestration_events: list[dict[str, Any]],
) -> BenchmarkComparisonMetric:
    if passed:
        return _metric(
            "failure_attribution_clarity",
            "not_applicable",
            None,
            reason="mode did not fail",
        )
    failed_observations = [
        observation
        for observation in _tool_observations(run_events)
        if observation.get("success") is False
    ]
    blocked_child = next(
        (
            event.get("payload", {}).get("blocked_child_id")
            for event in orchestration_events
            if event.get("payload", {}).get("blocked_child_id")
        ),
        None,
    )
    return _metric(
        "failure_attribution_clarity",
        "available",
        bool(failed_observations or blocked_child),
        details={
            "failed_tool_observations": len(failed_observations),
            "blocked_child_id": blocked_child,
        },
    )


def _tool_observations(
    events: list[dict[str, Any]],
    *,
    tool_name: str | None = None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "tool_observation":
            continue
        observation = event.get("payload", {}).get("observation")
        if not isinstance(observation, dict):
            continue
        if tool_name is not None and observation.get("tool_name") != tool_name:
            continue
        observations.append(observation)
    return observations


def _run_events(workspace: Path, run_id: str) -> list[dict[str, Any]]:
    events_path = workspace / ".agent-harness" / "runs" / run_id / "events.jsonl"
    if not events_path.exists():
        return []
    return [
        event
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for event in [json.loads(line)]
        if isinstance(event, dict)
    ]


def _object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _tool_activity_count(events: Any) -> int:
    if not isinstance(events, list):
        return 0
    return sum(
        1
        for event in events
        if isinstance(event, dict) and event.get("type") in {"model_action", "tool_observation"}
    )
