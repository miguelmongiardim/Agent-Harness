from __future__ import annotations

from typing import Any

_LAZY_EXPORTS = {
    "build_skill_manifest": ("agent_harness.skills.manifest", "build_skill_manifest"),
    "list_skills": ("agent_harness.skills.validation", "list_skills"),
    "load_skill_detail": ("agent_harness.skills.validation", "load_skill_detail"),
    "render_skill": ("agent_harness.skills.validation", "render_skill"),
    "resolve_task_skills": ("agent_harness.skills.resolution", "resolve_task_skills"),
    "skill_discovery_diagnostics": (
        "agent_harness.skills.validation",
        "skill_discovery_diagnostics",
    ),
    "validate_skill": ("agent_harness.skills.validation", "validate_skill"),
    "validate_skill_pack_path": (
        "agent_harness.skills.validation",
        "validate_skill_pack_path",
    ),
    "validate_skill_path": ("agent_harness.skills.validation", "validate_skill_path"),
}

__all__ = [
    "build_skill_manifest",
    "list_skills",
    "load_skill_detail",
    "render_skill",
    "resolve_task_skills",
    "skill_discovery_diagnostics",
    "validate_skill",
    "validate_skill_pack_path",
    "validate_skill_path",
]


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
