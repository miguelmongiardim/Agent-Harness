from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.templates.schema import TemplateFile
from agent_harness.utils import normalize_relative_path, now_utc

if TYPE_CHECKING:
    from agent_harness.tasks.schema import TaskSpec

BenchmarkKind = Literal["swe_bench_style", "terminal_task"]
BenchmarkAdapterId = Literal["swebench_style", "terminal_bench_style"]
RunStatus = Literal["completed", "paused", "failed", "dry_run"]
BenchmarkComparisonModeId = Literal[
    "single_agent_baseline",
    "planner_implementer",
    "planner_implementer_reviewer",
    "planner_implementer_reviewer_tester",
]
BenchmarkComparisonModeStatus = Literal["completed", "paused", "failed", "dry_run", "skipped"]
BenchmarkComparisonMetricStatus = Literal["available", "unavailable", "not_applicable"]
BenchmarkComparisonSuiteCaseStatus = Literal["completed", "failed"]
BenchmarkComparisonSuiteStatus = Literal["completed", "failed"]
BenchmarkComparisonRole = Literal["planner", "implementer", "reviewer", "tester"]
BenchmarkComparisonRoleRecommendationAction = Literal["retain", "neutral", "remove_candidate"]
BenchmarkComparisonDefaultRecommendation = Literal["not_recommended", "candidate"]
BenchmarkComparisonHandoffClassification = Literal[
    "included",
    "policy_denied",
    "budget_excluded",
    "included_but_unused",
    "used_by_downstream",
]


class BenchmarkCaseRecord(StrictModel):
    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    benchmark_kind: BenchmarkKind
    description: str = ""
    workspace_files: list[TemplateFile]
    task: Any
    retrieval_backend: Literal["lexical", "qdrant"] = "lexical"
    ingest_paths: list[str] = Field(default_factory=list)
    auto_approve_patches: bool = False
    expected_status: RunStatus = "completed"

    @field_validator("task", mode="before")
    @classmethod
    def validate_task(cls, value: Any) -> TaskSpec:
        from agent_harness.tasks.schema import TaskSpec

        if isinstance(value, TaskSpec):
            return value
        return TaskSpec.model_validate(value)

    @field_validator("ingest_paths")
    @classmethod
    def validate_ingest_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]


class BenchmarkAdapterEvidence(StrictModel):
    schema_version: Literal["benchmark_adapter_evidence.v1"] = "benchmark_adapter_evidence.v1"
    adapter_id: BenchmarkAdapterId
    task_import: dict[str, str]
    workspace_preparation: dict[str, str | list[str]]
    policy_selection: dict[str, str]
    run_execution: dict[str, str]
    eval_result_mapping: dict[str, str | bool]
    export: dict[str, str]
    retrieval: dict[str, str | bool] = Field(default_factory=dict)


class BenchmarkPackRecord(StrictModel):
    schema_version: Literal["benchmark_pack.v1"] = "benchmark_pack.v1"
    pack_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    cases: list[BenchmarkCaseRecord]

    @model_validator(mode="after")
    def validate_case_ids(self) -> BenchmarkPackRecord:
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("benchmark case_id values must be unique")
        return self


class BenchmarkResult(StrictModel):
    schema_version: Literal["benchmark_result.v1"] = "benchmark_result.v1"
    pack_id: str
    version: str
    case_id: str
    benchmark_kind: BenchmarkKind
    adapter_id: BenchmarkAdapterId
    run_id: str
    task_id: str
    status: RunStatus
    passed: bool
    workspace: str
    task_path: str
    result_artifact: str
    run_export: str
    run_artifacts: dict[str, str]
    adapter_evidence: BenchmarkAdapterEvidence
    approval_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class BenchmarkComparisonChildRun(StrictModel):
    child_id: str
    role: str
    run_id: str
    status: RunStatus
    run_summary_artifact: str


class BenchmarkComparisonMetric(StrictModel):
    schema_version: Literal["benchmark_comparison_metric.v1"] = "benchmark_comparison_metric.v1"
    name: str = Field(min_length=1)
    status: BenchmarkComparisonMetricStatus
    value: Any = None
    unit: str | None = None
    reason: str | None = None
    evidence: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkComparisonRoleRecommendation(StrictModel):
    schema_version: Literal["benchmark_comparison_role_recommendation.v1"] = (
        "benchmark_comparison_role_recommendation.v1"
    )
    role: BenchmarkComparisonRole
    recommendation: BenchmarkComparisonRoleRecommendationAction
    default_recommendation: BenchmarkComparisonDefaultRecommendation = "not_recommended"
    reason_codes: list[str] = Field(default_factory=list)
    supporting_metric_names: list[str] = Field(default_factory=list)
    compared_mode_id: BenchmarkComparisonModeId | None = None
    baseline_mode_id: BenchmarkComparisonModeId | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkComparisonHandoffUsefulness(StrictModel):
    schema_version: Literal["benchmark_comparison_handoff_usefulness.v1"] = (
        "benchmark_comparison_handoff_usefulness.v1"
    )
    handoff_id: str
    from_child_id: str
    to_child_id: str
    classification: BenchmarkComparisonHandoffClassification
    reason_codes: list[str] = Field(default_factory=list)
    supporting_metric_names: list[str] = Field(default_factory=list)
    supporting_artifacts: list[str] = Field(default_factory=list)


class BenchmarkComparisonModeResult(StrictModel):
    schema_version: Literal["benchmark_comparison_mode_result.v1"] = (
        "benchmark_comparison_mode_result.v1"
    )
    mode_id: BenchmarkComparisonModeId
    label: str
    execution_order: int
    status: BenchmarkComparisonModeStatus
    passed: bool
    eligible: bool = True
    skip_reason: str | None = None
    run_id: str | None = None
    benchmark_result: str | None = None
    run_export: str | None = None
    orchestration_id: str | None = None
    orchestration_export: str | None = None
    orchestration_summary: str | None = None
    child_runs: list[BenchmarkComparisonChildRun] = Field(default_factory=list)
    child_run_count: int = 0
    tool_call_count: int = 0
    handoff_count: int = 0
    artifact_completeness: dict[str, bool] = Field(default_factory=dict)
    metrics: list[BenchmarkComparisonMetric] = Field(default_factory=list)
    handoff_usefulness: list[BenchmarkComparisonHandoffUsefulness] = Field(
        default_factory=list
    )


class BenchmarkComparisonResult(StrictModel):
    schema_version: Literal["benchmark_comparison_result.v1"] = "benchmark_comparison_result.v1"
    pack_id: str
    version: str
    case_id: str
    benchmark_kind: BenchmarkKind
    baseline_mode_id: Literal["single_agent_baseline"] = "single_agent_baseline"
    result_artifact: str
    modes: list[BenchmarkComparisonModeResult]
    role_recommendations: list[BenchmarkComparisonRoleRecommendation] = Field(
        default_factory=list
    )
    created_at: datetime = Field(default_factory=now_utc)


class BenchmarkComparisonSuiteModeStatus(StrictModel):
    mode_id: BenchmarkComparisonModeId
    eligible: bool
    status: BenchmarkComparisonModeStatus
    passed: bool
    skip_reason: str | None = None


class BenchmarkComparisonSuiteCaseResult(StrictModel):
    schema_version: Literal["benchmark_comparison_suite_case.v1"] = (
        "benchmark_comparison_suite_case.v1"
    )
    case_id: str
    benchmark_kind: BenchmarkKind
    status: BenchmarkComparisonSuiteCaseStatus
    passed: bool
    comparison_result: str | None = None
    error: str | None = None
    mode_statuses: list[BenchmarkComparisonSuiteModeStatus] = Field(default_factory=list)


class BenchmarkComparisonSuiteResult(StrictModel):
    schema_version: Literal["benchmark_comparison_suite.v1"] = "benchmark_comparison_suite.v1"
    pack_id: str
    version: str
    status: BenchmarkComparisonSuiteStatus
    passed: bool
    result_artifact: str
    case_count: int
    cases: list[BenchmarkComparisonSuiteCaseResult]
    created_at: datetime = Field(default_factory=now_utc)
