from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SLOW_TEST_MODULES = {
    "tests/e2e/test_e2e_cli_lifecycle.py",
    "tests/e2e/test_provider_audit_demo.py",
    "tests/e2e/test_retrieval_quality_demo.py",
    "tests/e2e/test_runtime_resume.py",
    "tests/integration/test_provider_approval.py",
    "tests/integration/test_provider_gateway.py",
    "tests/integration/test_provider_input.py",
    "tests/integration/test_provider_profiles.py",
    "tests/integration/test_release_evidence.py",
    "tests/integration/test_retrieval_qdrant_local.py",
    "tests/integration/test_retrieval_qdrant_server.py",
    "tests/integration/test_retrieval_quality_release.py",
    "tests/integration/test_retrieval_scorecard.py",
}

GOLDEN_PATH_TEST_MODULES = {
    "tests/e2e/test_e2e_cli_lifecycle.py",
    "tests/e2e/test_provider_audit_demo.py",
    "tests/e2e/test_retrieval_quality_demo.py",
    "tests/e2e/test_runtime_resume.py",
}

RELEASE_GATE_TEST_MODULES = {
    "tests/integration/test_release_evidence.py",
}


def test_default_pytest_profile_excludes_slow_tests() -> None:
    options = _pytest_options()

    assert options["addopts"] == "-m 'not slow'"


def test_pytest_profile_markers_are_registered() -> None:
    markers = "\n".join(_pytest_options()["markers"])

    assert "slow:" in markers
    assert "release_gate:" in markers
    assert "golden_path:" in markers


def test_heavy_test_modules_are_marked_slow() -> None:
    for relative_path in sorted(SLOW_TEST_MODULES):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        assert "pytestmark" in text, relative_path
        assert "pytest.mark.slow" in text, relative_path


def test_e2e_modules_are_marked_as_golden_paths() -> None:
    for relative_path in sorted(GOLDEN_PATH_TEST_MODULES):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        assert "pytest.mark.golden_path" in text, relative_path


def test_release_evidence_module_is_an_explicit_release_gate() -> None:
    for relative_path in sorted(RELEASE_GATE_TEST_MODULES):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

        assert "pytest.mark.release_gate" in text, relative_path


def test_ci_runs_slow_release_gate_explicitly() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert '-m "slow and release_gate"' in workflow


def _pytest_options() -> dict[str, object]:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["tool"]["pytest"]["ini_options"]
