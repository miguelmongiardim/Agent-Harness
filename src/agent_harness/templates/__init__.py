from __future__ import annotations

from typing import Any

_LAZY_EXPORTS = {
    "list_templates": ("agent_harness.templates.registry", "list_templates"),
    "load_template": ("agent_harness.templates.registry", "load_template"),
    "load_template_record": ("agent_harness.templates.registry", "load_template_record"),
    "plan_template_apply": ("agent_harness.templates.apply", "plan_template_apply"),
}

__all__ = [
    "list_templates",
    "load_template",
    "load_template_record",
    "plan_template_apply",
]


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
