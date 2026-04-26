from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from agent_harness.schemas import PolicyProfile
from agent_harness.utils import normalize_relative_path


def denied_glob(profile: PolicyProfile, relative: str) -> str | None:
    for pattern in profile.deny_globs:
        if matches_glob(relative, pattern):
            return pattern
    return None


def matches_glob(relative: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/")
    if fnmatch.fnmatch(relative, normalized):
        return True
    return normalized.startswith("**/") and fnmatch.fnmatch(relative, normalized[3:])


def is_within_roots(project_root: Path, relative: str, roots: list[str]) -> bool:
    target = (project_root / relative).resolve()
    for root in roots:
        root_path = (project_root / root).resolve()
        try:
            if os.path.commonpath([str(target), str(root_path)]) == str(root_path):
                return True
        except ValueError:
            continue
    return False


def resolve_relative(project_root: Path, path: str) -> Path:
    relative = normalize_relative_path(path)
    return (project_root / relative).resolve()
