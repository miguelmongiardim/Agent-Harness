from __future__ import annotations

from pathlib import Path

from agent_harness.config import load_public_model
from agent_harness.orchestration.schema import OrchestrationSpec


def load_orchestration_spec(path: Path) -> OrchestrationSpec:
    return load_public_model(path, OrchestrationSpec)
