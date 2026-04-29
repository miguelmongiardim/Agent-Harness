from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["DeterministicMockModel", "ModelClient"]

_LAZY_EXPORTS = {
    "DeterministicMockModel": ("agent_harness.model.mock", "DeterministicMockModel"),
    "ModelClient": ("agent_harness.model.base", "ModelClient"),
}


if TYPE_CHECKING:
    from agent_harness.model.base import ModelClient
    from agent_harness.model.mock import DeterministicMockModel


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
