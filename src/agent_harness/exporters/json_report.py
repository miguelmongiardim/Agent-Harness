from __future__ import annotations

from pathlib import Path

from agent_harness.storage import RunStore
from agent_harness.utils import write_json


def export_json(store: RunStore, output: Path) -> Path:
    write_json(
        output,
        {
            "schema_version": "run_export.v1",
            "run_id": store.run_id,
            "summary": store.read_data("summary.json"),
            "artifact_index": store.read_data("artifact-index.json"),
            "events": store.events(),
        },
    )
    return output
