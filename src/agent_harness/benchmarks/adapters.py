from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent_harness.schemas import (
    BenchmarkAdapterEvidence,
    BenchmarkAdapterId,
    BenchmarkCaseRecord,
    BenchmarkKind,
    RunStatus,
)


@dataclass(frozen=True)
class BenchmarkAdapterContext:
    case: BenchmarkCaseRecord
    workspace: str
    task_path: str
    run_id: str
    status: RunStatus
    passed: bool
    result_artifact: str
    run_export: str
    retrieval: dict[str, str | bool]


class BenchmarkAdapter(Protocol):
    @property
    def adapter_id(self) -> BenchmarkAdapterId:
        ...

    @property
    def benchmark_kind(self) -> BenchmarkKind:
        ...

    def evidence(self, context: BenchmarkAdapterContext) -> BenchmarkAdapterEvidence:
        ...


@dataclass(frozen=True)
class LocalBenchmarkAdapter:
    adapter_id: BenchmarkAdapterId
    benchmark_kind: BenchmarkKind

    def evidence(self, context: BenchmarkAdapterContext) -> BenchmarkAdapterEvidence:
        return BenchmarkAdapterEvidence(
            adapter_id=self.adapter_id,
            task_import={
                "task_id": context.case.task.task_id,
                "task_path": context.task_path,
            },
            workspace_preparation={
                "workspace": context.workspace,
                "workspace_files": [file.path for file in context.case.workspace_files],
            },
            policy_selection={
                "profile": context.case.task.policy_profile,
                "policy_path": f"policies/{context.case.task.policy_profile}.json",
            },
            run_execution={
                "run_id": context.run_id,
                "status": context.status,
            },
            eval_result_mapping={
                "expected_status": context.case.expected_status,
                "actual_status": context.status,
                "passed": context.passed,
            },
            export={
                "result_artifact": context.result_artifact,
                "run_export": context.run_export,
            },
            retrieval=context.retrieval,
        )


def adapter_for_case(case: BenchmarkCaseRecord) -> BenchmarkAdapter:
    if case.benchmark_kind == "swe_bench_style":
        return LocalBenchmarkAdapter(
            adapter_id="swebench_style",
            benchmark_kind="swe_bench_style",
        )
    return LocalBenchmarkAdapter(
        adapter_id="terminal_bench_style",
        benchmark_kind="terminal_task",
    )
