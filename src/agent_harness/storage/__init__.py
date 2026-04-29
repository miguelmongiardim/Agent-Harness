from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["RunStore", "make_event"]

_LAZY_EXPORTS = {
    "RunStore": ("agent_harness.storage.runs", "RunStore"),
    "make_event": ("agent_harness.storage.runs", "make_event"),
}


if TYPE_CHECKING:
    from agent_harness.storage.runs import RunStore, make_event


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
