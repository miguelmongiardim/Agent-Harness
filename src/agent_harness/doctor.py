from __future__ import annotations

import importlib.util
import platform
import shutil
from pathlib import Path

from agent_harness.config import load_config


def doctor(project_root: Path) -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True
    messages.append(f"OK python: {platform.python_version()}")

    if importlib.util.find_spec("pydantic") is None:
        ok = False
        messages.append("FAIL pydantic: not installed")
    else:
        messages.append("OK pydantic")

    if shutil.which("uv") is None:
        messages.append("WARN uv: not on PATH")
    else:
        messages.append("OK uv")

    config_path = project_root / "agent-harness.yaml"
    if config_path.exists():
        config = load_config(project_root)
        messages.append(f"OK config: {config_path.name} artifact_root={config.artifact_root}")
    else:
        ok = False
        messages.append("FAIL config: agent-harness.yaml missing")

    policy_path = project_root / "policies" / "default.json"
    if policy_path.exists():
        messages.append("OK policy: default")
    else:
        ok = False
        messages.append("FAIL policy: policies/default.json missing")

    if importlib.util.find_spec("qdrant_client") and importlib.util.find_spec("fastembed"):
        messages.append("OK optional retrieval: qdrant-client + fastembed")
    else:
        messages.append(
            "WARN optional retrieval: qdrant-client/fastembed unavailable; lexical fallback active"
        )
    messages.append("OK first-party security checks active")
    if importlib.util.find_spec("bandit") or shutil.which("bandit"):
        messages.append("OK optional scanner: bandit available")
    else:
        messages.append(
            "WARN optional scanner: bandit unavailable; first-party security checks active"
        )
    return ok, messages
