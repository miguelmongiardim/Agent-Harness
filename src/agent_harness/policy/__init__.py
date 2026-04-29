from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["PolicyEngine", "PolicyError", "load_policy", "load_policy_with_schema_evidence"]

_LAZY_EXPORTS = {
    "PolicyEngine": ("agent_harness.policy.engine", "PolicyEngine"),
    "PolicyError": ("agent_harness.policy.engine", "PolicyError"),
    "load_policy": ("agent_harness.policy.engine", "load_policy"),
    "load_policy_with_schema_evidence": (
        "agent_harness.policy.engine",
        "load_policy_with_schema_evidence",
    ),
}


if TYPE_CHECKING:
    from agent_harness.policy.engine import (
        PolicyEngine,
        PolicyError,
        load_policy,
        load_policy_with_schema_evidence,
    )


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
