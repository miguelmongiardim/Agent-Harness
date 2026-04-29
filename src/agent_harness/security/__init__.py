from __future__ import annotations

from typing import Any

__all__ = ["collect_advisory_reports", "scan_task_security"]

_LAZY_EXPORTS = {
    "collect_advisory_reports": ("agent_harness.security.advisory", "collect_advisory_reports"),
    "scan_task_security": ("agent_harness.security.scanner", "scan_task_security"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
