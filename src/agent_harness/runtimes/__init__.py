from __future__ import annotations

from typing import Any

__all__ = ["HarnessRuntime", "approve_action"]

_LAZY_EXPORTS = {
    "HarnessRuntime": ("agent_harness.runtimes.native", "HarnessRuntime"),
    "approve_action": ("agent_harness.runtimes.native", "approve_action"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
