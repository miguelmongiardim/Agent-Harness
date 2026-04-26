from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.utils import hash_file

_ADVISORY_INPUTS = {
    "gitleaks": "gitleaks.json",
    "cyclonedx": "cyclonedx.json",
}


def collect_advisory_reports(project_root: Path, artifact_root: Path) -> dict[str, Any] | None:
    advisory_dir = artifact_root / "advisories"
    reports: list[dict[str, Any]] = []
    for kind, filename in _ADVISORY_INPUTS.items():
        path = advisory_dir / filename
        if not path.exists() or not path.is_file():
            continue
        reports.append(
            {
                "kind": kind,
                "available": True,
                "policy_action": "advisory",
                "blocking": False,
                "path": path.relative_to(project_root).as_posix(),
                "content_hash": hash_file(path),
            }
        )
    if not reports:
        return None
    return {
        "schema_version": "advisory_reports.v1",
        "status": "recorded",
        "reports": reports,
    }
