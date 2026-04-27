from __future__ import annotations

from pathlib import Path


def test_ci_workflow_runs_release_maturity_gates() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    required_commands = [
        "python -m pre_commit run --all-files",
        "python -m pytest -q",
        "python -m agent_harness docs check",
        "python -m agent_harness release package-check",
        "python -m agent_harness demo provider-audit",
        "python -m agent_harness run examples/tasks/python_refactor.json --dry-run",
        "python -m agent_harness template validate --all",
        "python -m agent_harness release readiness",
    ]

    for command in required_commands:
        assert command in workflow

    assert "actions/upload-artifact" in workflow
    assert ".agent-harness/release" in workflow
    assert "dist/" in workflow


def test_ci_workflow_uses_node24_ready_action_versions() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "actions/checkout@v6" in workflow
    assert "actions/setup-python@v6" in workflow
    assert "actions/upload-artifact@v6" in workflow
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow
    assert "actions/upload-artifact@v4" not in workflow


def test_pre_commit_config_is_local_practical_and_documented() -> None:
    config = Path(".pre-commit-config.yaml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    docs = "\n".join(
        [
            Path("README.md").read_text(encoding="utf-8"),
            Path("docs/release-readiness.md").read_text(encoding="utf-8"),
        ]
    )

    assert "repo: local" in config
    for hook_id in (
        "ruff-check",
        "ruff-format-check",
        "mypy",
        "docs-check",
        "compileall",
        "no-large-files",
        "private-key-guard",
    ):
        assert f"id: {hook_id}" in config

    assert '"pre-commit>=' in pyproject
    assert "python -m pre_commit run --all-files" in docs
    assert "large file guard" in docs
    assert "private key guard" in docs


def test_advisory_scanners_are_visible_optional_ci_evidence() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")

    assert "advisory-evidence:" in workflow
    assert "continue-on-error: true" in workflow
    assert "gitleaks detect" in workflow
    assert "cyclonedx-py" in workflow
    assert ".agent-harness/advisories/gitleaks.json" in workflow
    assert ".agent-harness/advisories/cyclonedx.json" in workflow

    assert "advisory" in docs.lower()
    assert "optional" in docs.lower()
    assert "must not block" in docs
