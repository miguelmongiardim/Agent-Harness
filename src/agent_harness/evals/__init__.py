from __future__ import annotations

from typing import Any

__all__ = [
    "BUILTIN_EVALS",
    "run_builtin_evals",
    "run_eval_spec",
    "write_eval_report",
]

_LAZY_EXPORTS = {
    "BUILTIN_EVALS": ("agent_harness.evals.runner", "BUILTIN_EVALS"),
    "run_builtin_evals": ("agent_harness.evals.runner", "run_builtin_evals"),
    "run_eval_spec": ("agent_harness.evals.runner", "run_eval_spec"),
    "write_eval_report": ("agent_harness.evals.runner", "write_eval_report"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
