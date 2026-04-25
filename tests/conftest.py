from __future__ import annotations

import json
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY


def seed_project(root: Path) -> None:
    (root / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v1",
                "project_name: test-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8"
    )
