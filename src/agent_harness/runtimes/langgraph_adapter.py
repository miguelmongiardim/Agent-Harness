from __future__ import annotations

from importlib import import_module
from pathlib import Path

from agent_harness.core.exceptions import UnsupportedAdapterError
from agent_harness.core.runtime import HarnessRuntime
from agent_harness.storage.schema import RunSummary


def run_langgraph_adapter(
    project_root: Path,
    task_path: Path,
    profile_name: str | None = None,
    provider_name: str | None = None,
    deny_provider_input: list[str] | None = None,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> RunSummary:
    _require_langgraph()
    return HarnessRuntime(project_root).run_task(
        task_path,
        profile_name=profile_name,
        provider_name=provider_name,
        deny_provider_input=deny_provider_input,
        auto_approve=auto_approve,
        dry_run=dry_run,
        runtime_adapter="langgraph",
    )


def _require_langgraph() -> None:
    try:
        import_module("langgraph")
    except ModuleNotFoundError as exc:
        raise UnsupportedAdapterError(
            "LangGraph runtime requires the optional langgraph extra"
        ) from exc
