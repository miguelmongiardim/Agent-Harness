"""Local operator API boundary."""

from __future__ import annotations

from typing import Any

__all__ = ["create_operator_app"]

_LAZY_EXPORTS = {
    "create_operator_app": ("agent_harness.operator.app", "create_operator_app"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
