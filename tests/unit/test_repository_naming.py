from __future__ import annotations

import pathlib
import re

ROADMAP_NAME_PATTERN = re.compile(
    r"(^|[-_])v[0-9]+($|[-_.])|(^|[-_])phase([0-9]+)?($|[-_.])",
    re.IGNORECASE,
)


def test_tests_and_scripts_use_behavior_names() -> None:
    checked_roots = [pathlib.Path("tests")]
    scripts_root = pathlib.Path("scripts")
    if scripts_root.exists():
        checked_roots.append(scripts_root)

    roadmap_named_files = [
        path
        for root in checked_roots
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ROADMAP_NAME_PATTERN.search(path.name)
    ]

    assert roadmap_named_files == []
