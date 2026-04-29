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
