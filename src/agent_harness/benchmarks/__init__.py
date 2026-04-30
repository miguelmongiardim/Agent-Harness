from __future__ import annotations

from typing import Any

__all__ = [
    "list_benchmark_packs",
    "load_benchmark_pack",
    "run_benchmark_comparison",
    "run_benchmark_comparison_suite",
    "run_benchmark_case",
]

_LAZY_EXPORTS = {
    "list_benchmark_packs": ("agent_harness.benchmarks.packs", "list_benchmark_packs"),
    "load_benchmark_pack": ("agent_harness.benchmarks.packs", "load_benchmark_pack"),
    "run_benchmark_comparison": (
        "agent_harness.benchmarks.comparison",
        "run_benchmark_comparison",
    ),
    "run_benchmark_comparison_suite": (
        "agent_harness.benchmarks.comparison",
        "run_benchmark_comparison_suite",
    ),
    "run_benchmark_case": ("agent_harness.benchmarks.packs", "run_benchmark_case"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
