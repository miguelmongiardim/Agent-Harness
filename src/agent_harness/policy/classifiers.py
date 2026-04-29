from __future__ import annotations

import fnmatch

from agent_harness.policy.schema import PolicyProfile


def classify_path(profile: PolicyProfile, path: str | None) -> str:
    if path is None:
        return "unknown"
    relative = path.replace("\\", "/")
    for rule in profile.sensitivity_rules:
        if fnmatch.fnmatch(relative, rule.pattern):
            return rule.classification
    return "internal"
