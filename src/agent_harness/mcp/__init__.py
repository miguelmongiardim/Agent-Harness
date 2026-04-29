from __future__ import annotations

from typing import Any

__all__ = [
    "get_mcp_prompt",
    "list_mcp_prompts",
    "list_mcp_resources",
    "read_mcp_resource",
]

_LAZY_EXPORTS = {
    "get_mcp_prompt": ("agent_harness.mcp.prompts", "get_mcp_prompt"),
    "list_mcp_prompts": ("agent_harness.mcp.prompts", "list_mcp_prompts"),
    "list_mcp_resources": ("agent_harness.mcp.resources", "list_mcp_resources"),
    "read_mcp_resource": ("agent_harness.mcp.resources", "read_mcp_resource"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
