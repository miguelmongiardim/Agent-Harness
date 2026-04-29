from __future__ import annotations

import ast
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


def test_template_schema_module_owns_template_contracts() -> None:
    from agent_harness.templates.schema import (
        TemplateApplyRecord,
        TemplateDetail,
        TemplateFile,
        TemplateProposedWrite,
        TemplateRegistryRecord,
        TemplateSpec,
    )

    template_contracts = [
        TemplateApplyRecord,
        TemplateDetail,
        TemplateFile,
        TemplateProposedWrite,
        TemplateRegistryRecord,
        TemplateSpec,
    ]
    assert {contract.__module__ for contract in template_contracts} == {
        "agent_harness.templates.schema"
    }


def test_template_package_imports_template_contracts_from_owner_module() -> None:
    offenders: list[str] = []
    template_names = {
        "TemplateApplyRecord",
        "TemplateDetail",
        "TemplateFile",
        "TemplateProposedWrite",
        "TemplateRegistryRecord",
        "TemplateSpec",
    }
    for path in (PROJECT_ROOT / "src" / "agent_harness" / "templates").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "agent_harness.schemas":
                continue
            imported = {alias.name for alias in node.names}
            template_imports = sorted(imported & template_names)
            if template_imports:
                relative_path = path.relative_to(PROJECT_ROOT).as_posix()
                offenders.append(f"{relative_path}: {', '.join(template_imports)}")

    assert offenders == []


def test_root_schema_template_names_reexport_owner_contracts_during_transition() -> None:
    from agent_harness.schemas import TemplateSpec as RootTemplateSpec
    from agent_harness.templates.schema import TemplateSpec

    assert RootTemplateSpec is TemplateSpec
