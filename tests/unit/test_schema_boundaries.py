from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.xfail(
    strict=True,
    reason="V10 Phase 0 guard: Phase 4 removes agent_harness.schemas",
)
def test_root_schema_aggregator_is_removed() -> None:
    root_schema = PROJECT_ROOT / "src" / "agent_harness" / "schemas.py"
    assert not root_schema.exists(), "agent_harness.schemas must not be reintroduced"

    offenders = []
    for search_root in (PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
        for path in search_root.rglob("*.py"):
            if path == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            if "agent_harness.schemas" in text:
                offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []
