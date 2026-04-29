from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "PatchFileArgs",
    "ReadFileArgs",
    "RunTestsArgs",
    "SearchCodeArgs",
    "ToolArgs",
    "ToolExecutor",
]

_LAZY_EXPORTS = {
    "PatchFileArgs": ("agent_harness.tools.patch_file", "PatchFileArgs"),
    "ReadFileArgs": ("agent_harness.tools.read_file", "ReadFileArgs"),
    "RunTestsArgs": ("agent_harness.tools.run_tests", "RunTestsArgs"),
    "SearchCodeArgs": ("agent_harness.tools.search_code", "SearchCodeArgs"),
    "ToolArgs": ("agent_harness.tools.registry", "ToolArgs"),
    "ToolExecutor": ("agent_harness.tools.executor", "ToolExecutor"),
}


if TYPE_CHECKING:
    from agent_harness.tools.executor import ToolExecutor
    from agent_harness.tools.patch_file import PatchFileArgs
    from agent_harness.tools.read_file import ReadFileArgs
    from agent_harness.tools.registry import ToolArgs
    from agent_harness.tools.run_tests import RunTestsArgs
    from agent_harness.tools.search_code import SearchCodeArgs


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
