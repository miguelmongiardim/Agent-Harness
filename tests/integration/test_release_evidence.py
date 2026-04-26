from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_harness import release
from agent_harness.cli import main
from tests.conftest import seed_project


def test_release_readiness_report_requires_docs_checks_ci_advisories_and_changelog(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["release", "readiness", "--version", "0.3.0"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "release_readiness.v1"
    assert report["version"] == "0.3.0"
    assert report["tag"]["name"] == "v0.3.0"
    assert report["tag"]["target_commit"]
    assert report["changelog"]["entry"] == "0.3.0"
    assert report["changelog"]["present"] is True
    assert report["docs_gate"]["command"] == "agent-harness docs check"
    assert report["docs_gate"]["status"] in {"passed", "failed"}

    local_checks = report["local_checks"]
    assert set(local_checks) == {
        "pytest",
        "docs_check",
        "ruff",
        "mypy",
        "compileall",
        "diff_check",
        "eval",
    }
    assert all(check["command"] for check in local_checks.values())

    remote_ci = report["remote_ci"]
    assert remote_ci["python_3_11"]["required"] is True
    assert remote_ci["python_3_12"]["required"] is True
    assert remote_ci["python_3_13"]["allowed_failure"] is True

    advisory = report["advisory_reports"]
    assert advisory["gitleaks"]["required"] is False
    assert advisory["cyclonedx"]["required"] is False
    assert advisory["gitleaks"]["path"].endswith("gitleaks.json")
    assert advisory["cyclonedx"]["path"].endswith("cyclonedx.json")

    assert report["status"] in {"ready", "pending"}
    assert Path(report["report_path"]).exists()


def test_release_readiness_defaults_to_project_version_and_reports_missing_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "0.3.0")

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["version"] == "0.3.0"
    assert report["status"] == "pending"

    assert report["package"]["build"]["command"] == "python -m build"
    assert report["package"]["clean_install"]["command"].startswith("python -m pip install")
    assert report["package"]["console_script"]["command"] == "agent-harness doctor"

    assert report["demos"]["provider-audit"]["command"] == "agent-harness demo provider-audit"
    assert report["demos"]["python-refactor"]["command"].startswith("agent-harness run")

    assert report["docs"]["check"]["status"] in {"passed", "failed"}
    assert report["docs"]["schema_compatibility"]["path"] == "docs/prd-agent-harness-v3.md"
    assert report["docs"]["schema_compatibility"]["present"] is True
    assert report["docs"]["roadmap_claims"]["status"] in {"passed", "failed"}

    assert report["templates"]["validation"]["command"] == "agent-harness template validate --all"
    assert report["release_artifacts"]["wheel"]["expected_glob"] == (
        "dist/agent_harness-0.3.0-*.whl"
    )
    assert report["release_artifacts"]["sdist"]["expected_glob"] == (
        "dist/agent_harness-0.3.0.tar.gz"
    )

    missing = [entry for entry in report["diagnostics"] if entry["status"] != "passed"]
    assert missing
    assert all(entry["action"] for entry in missing)


def test_release_readiness_reports_ready_when_required_evidence_is_present(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(
        release,
        "_remote_ci_evidence",
        lambda project_root, target_commit, ci_run_id: {
            "run": {
                "source": "github_actions",
                "status": "completed",
                "conclusion": "success",
                "matches_target_commit": True,
            },
            "python_3_11": {"required": True, "status": "passed"},
            "python_3_12": {"required": True, "status": "passed"},
            "python_3_13": {"allowed_failure": True, "status": "failed_allowed"},
        },
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["version"] == "9.9.9"
    assert report["status"] == "ready"
    assert report["diagnostics"] == []
    assert report["package"]["build"]["status"] == "passed"
    assert report["package"]["clean_install"]["status"] == "passed"
    assert report["package"]["console_script"]["status"] == "passed"
    assert report["demos"]["provider-audit"]["status"] == "passed"
    assert report["templates"]["validation"]["status"] == "passed"


def test_release_package_check_builds_installs_and_records_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    commands: list[list[str]] = []

    def fake_run_command(
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del timeout_seconds
        commands.append(command)
        if command[1:3] == ["-m", "build"]:
            dist = cwd / "dist"
            dist.mkdir(exist_ok=True)
            (dist / "agent_harness-9.9.9-py3-none-any.whl").write_text(
                "wheel", encoding="utf-8"
            )
            (dist / "agent_harness-9.9.9.tar.gz").write_text("sdist", encoding="utf-8")
        return {
            "command": " ".join(command),
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
            "status": "passed",
        }

    monkeypatch.setattr(release, "_run_command", fake_run_command, raising=False)

    assert main(["release", "package-check"]) == 0
    package_report = json.loads(capsys.readouterr().out)

    assert package_report["schema_version"] == "release_package_check.v1"
    assert package_report["status"] == "passed"
    assert package_report["version"] == "9.9.9"
    assert package_report["artifacts"]["wheel"]["sha256"]
    assert package_report["artifacts"]["sdist"]["sha256"]
    assert any(command[1:5] == ["-m", "build", "--outdir", "dist"] for command in commands)
    assert any(command[1:3] == ["-m", "venv"] for command in commands)
    assert any(command[1:4] == ["-m", "pip", "install"] for command in commands)
    assert any(command[-1] == "doctor" and "agent-harness" in command[-2] for command in commands)

    evidence_dir = tmp_path / ".agent-harness" / "release" / "evidence"
    assert json.loads((evidence_dir / "package-build.json").read_text())["status"] == "passed"
    assert json.loads((evidence_dir / "clean-install.json").read_text())["status"] == "passed"
    assert json.loads((evidence_dir / "console-script.json").read_text())["status"] == "passed"

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["package"]["build"]["status"] == "passed"
    assert readiness["package"]["clean_install"]["status"] == "passed"
    assert readiness["package"]["console_script"]["status"] == "passed"


def test_packaging_docs_cover_uv_sync_and_package_install_paths() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{release_docs}"

    assert "uv sync --extra dev" in combined
    assert "python -m pip install ." in combined
    assert "agent-harness release package-check" in combined


def test_demo_docs_cover_provider_audit_and_secondary_python_refactor_paths() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    provider_demo = Path("examples/provider_audit/README.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{provider_demo}\n{release_docs}"

    assert "agent-harness demo provider-audit" in combined
    assert "agent-harness run examples/tasks/python_refactor.json --dry-run" in combined
    assert "demo-python-refactor.json" in combined


def test_template_validation_satisfies_release_readiness_template_gate(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")

    assert main(["template", "validate", "--all"]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["status"] == "passed"
    assert len(evidence["templates"]) == 3

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["templates"]["validation"]["status"] == "passed"
    assert readiness["templates"]["validation"]["evidence"] == (
        ".agent-harness/release/evidence/template-validation.json"
    )


def _write_release_ready_project(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "agent-harness"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Agent Harness",
                "",
                "## What This Repo Proves",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## Roadmap / Not Enabled By Init",
                "",
                "Roadmap features remain future scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "prd-agent-harness-v3.md").write_text(
        "\n".join(
            [
                "# Agent Harness V3 / v1.0.0 PRD",
                "",
                "Agent Harness V3 is the v1.0.0 maturity release.",
                "",
                "## Compatibility And Deprecation Policy",
                "",
                "V2 schemas are the v1.0.0 public baseline.",
                "",
                "## Implemented vs Roadmap",
                "",
                "Implemented capabilities are separate from roadmap scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-04-26\n\n- Release.\n",
        encoding="utf-8",
    )
    dist = root / "dist"
    dist.mkdir()
    (dist / f"agent_harness-{version}-py3-none-any.whl").write_text(
        "wheel", encoding="utf-8"
    )
    (dist / f"agent_harness-{version}.tar.gz").write_text("sdist", encoding="utf-8")
    evidence = root / ".agent-harness" / "release" / "evidence"
    evidence.mkdir(parents=True)
    for name in (
        "package-build",
        "clean-install",
        "console-script",
        "demo-provider-audit",
        "demo-python-refactor",
        "template-validation",
    ):
        (evidence / f"{name}.json").write_text(
            json.dumps({"status": "passed"}), encoding="utf-8"
        )


def _write_release_project_without_evidence(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "agent-harness"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Agent Harness",
                "",
                "## What This Repo Proves",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## Roadmap / Not Enabled By Init",
                "",
                "Roadmap features remain future scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "prd-agent-harness-v3.md").write_text(
        "\n".join(
            [
                "# Agent Harness V3 / v1.0.0 PRD",
                "",
                "Agent Harness V3 is the v1.0.0 maturity release.",
                "",
                "## Compatibility And Deprecation Policy",
                "",
                "V2 schemas are the v1.0.0 public baseline.",
                "",
                "## Implemented vs Roadmap",
                "",
                "Implemented capabilities are separate from roadmap scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-04-26\n\n- Release.\n",
        encoding="utf-8",
    )
