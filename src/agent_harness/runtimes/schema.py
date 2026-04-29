from __future__ import annotations

from typing import Literal

from agent_harness.schema_base import StrictModel

RuntimeAdapterId = Literal["langgraph"]
RuntimeExecutionBoundary = Literal["native_runtime_delegate"]


class RuntimeAdapterRecord(StrictModel):
    schema_version: Literal["runtime_adapter.v1"] = "runtime_adapter.v1"
    adapter_id: RuntimeAdapterId
    execution_boundary: RuntimeExecutionBoundary = "native_runtime_delegate"
    package: str = "langgraph"
    package_present: bool = True
    run_id: str
    task_id: str
