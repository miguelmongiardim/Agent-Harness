from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from agent_harness import __version__, release
from agent_harness.cli import main
from tests.conftest import seed_project


def test_release_readiness_report_requires_docs_checks_ci_advisories_and_changelog(
    capsys: pytest.CaptureFixture[str],
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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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


def test_release_readiness_reports_operator_evidence_and_requires_packaged_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "1.3.0")

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    operator = report["operator"]
    assert operator["app_factory"]["status"] == "passed"
    assert operator["api_smoke"]["status"] == "passed"
    assert operator["token_required"]["status"] == "passed"
    assert operator["host_rejection"]["status"] == "passed"
    assert operator["approval_binding"]["status"] == "passed"
    assert operator["static_ui"]["status"] == "missing_evidence"
    assert operator["static_ui"]["missing_package_data"] == [
        "operator/static/*.html",
        "operator/static/*.css",
        "operator/static/*.js",
    ]
    assert operator["static_ui"]["remote_markers"] == []
    assert "operator.static_ui" in {entry["gate"] for entry in report["diagnostics"]}


def test_release_readiness_reports_ready_when_required_evidence_is_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
    assert all(entry["status"] == "passed" for entry in report["operator"].values())


def test_release_readiness_runs_v7_bundled_template_pack_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
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

    assert report["status"] == "ready"
    templates = report["templates"]
    assert templates["bundled_pack_acceptance"]["status"] == "passed"
    assert templates["bundled_pack_acceptance"]["template_ids"] == [
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    ]
    assert templates["remote_catalog_defaults"]["status"] == "passed"
    assert templates["remote_catalog_defaults"]["remote_defaults"] == []

    for pack in templates["bundled_pack_acceptance"]["packs"]:
        assert pack["validation"]["status"] == "passed"
        assert pack["dry_run"]["status"] == "passed"
        assert pack["clean_apply"]["status"] == "passed"
        assert pack["generated_examples"]["status"] == "passed"
        assert pack["application_evidence"]["status"] == "passed"
        assert pack["docs"]["status"] == "passed"


def test_v7_template_pack_golden_path_example_and_cli_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "examples" / "template_pack_system" / "README.md"
    text = readme.read_text(encoding="utf-8")

    for command in (
        "agent-harness template list",
        "agent-harness template show python-lib",
        "agent-harness template validate python-lib",
        "agent-harness template apply python-lib --target ./scratch/python-lib --dry-run",
        "agent-harness template apply python-lib --target ./scratch/python-lib --preview-diff",
        "agent-harness template apply python-lib --target ./scratch/python-lib",
        "agent-harness release readiness",
    ):
        assert command in text

    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["template", "list"]) == 0
    listed = capsys.readouterr().out
    assert "python-lib" in listed
    assert "bundled_pack" in listed

    assert main(["template", "show", "python-lib"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["template_id"] == "python-lib"
    assert shown["source_type"] == "bundled_pack"

    assert main(["template", "validate", "python-lib"]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "passed"

    target = tmp_path / "scratch" / "python-lib"
    assert main(["template", "apply", "python-lib", "--target", str(target), "--dry-run"]) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["status"] == "planned"
    assert not (target / "pyproject.toml").exists()

    assert (
        main(["template", "apply", "python-lib", "--target", str(target), "--preview-diff"])
        == 0
    )
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "preview_diff"
    assert preview["preview_diffs"]
    assert not (target / "pyproject.toml").exists()

    assert main(["template", "apply", "python-lib", "--target", str(target)]) == 0
    apply_summary = json.loads(capsys.readouterr().out)
    assert apply_summary["status"] == "completed"
    assert (target / "pyproject.toml").exists()

    assert main(["release", "readiness", "--version", "9.9.9"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["templates"]["bundled_pack_acceptance"]["status"] == "passed"
    assert readiness["templates"]["remote_catalog_defaults"]["status"] == "passed"


def test_release_readiness_rejects_remote_template_catalog_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "1.3.0")
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: remote-template-default",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: https://templates.example.invalid/catalog.json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    remote_defaults = report["templates"]["remote_catalog_defaults"]
    assert remote_defaults["status"] == "failed"
    assert remote_defaults["remote_defaults"] == [
        {
            "path": "agent-harness.yaml",
            "setting": "template_catalog",
            "value": "https://templates.example.invalid/catalog.json",
        }
    ]
    assert "templates.remote_catalog_defaults" in {
        entry["gate"] for entry in report["diagnostics"]
    }


def test_release_readiness_requires_v1_release_closure_docs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "1.0.0")
    for path in (tmp_path / "docs" / "migration.md", tmp_path / "docs" / "release-readiness.md"):
        path.unlink(missing_ok=True)
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

    assert report["status"] == "pending"
    assert report["docs"]["migration_notes"]["status"] == "missing_evidence"
    assert report["docs"]["release_process"]["status"] == "missing_evidence"
    diagnostic_gates = {entry["gate"] for entry in report["diagnostics"]}
    assert {"docs.migration_notes", "docs.release_process"} <= diagnostic_gates


def test_current_release_metadata_and_v1_closure_docs_are_complete() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "1.4.0"
    assert __version__ == "1.4.0"

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.4.0]" in changelog
    assert "## [1.3.0]" in changelog
    assert "## [1.2.0]" in changelog
    assert "## [1.1.0]" in changelog
    assert "## [1.0.0]" in changelog

    migration = Path("docs/migration.md").read_text(encoding="utf-8")
    assert "v0.3.0" in migration
    assert "v1.0.0" in migration
    assert "public compatibility baseline" in migration

    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    for marker in ("Release Checklist", "Tag Process", "Artifact Verification"):
        assert marker in release_docs


def test_ci_installs_operator_extra_and_runs_operator_release_gates() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pip install -e .[dev,operator]" in workflow
    assert "tests/integration/test_operator_cli.py" in workflow
    assert "tests/integration/test_operator_api.py" in workflow
    assert "tests/integration/test_operator_ui.py" in workflow
    assert "tests/integration/test_release_evidence.py" in workflow


def test_operator_release_docs_cover_v6_golden_path_and_evidence() -> None:
    operator_docs = Path("docs/operator-ui.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{operator_docs}\n{release_docs}"

    assert "uv sync --extra operator" in combined
    assert "uv run agent-harness demo provider-audit" in combined
    assert "uv run agent-harness serve --host 127.0.0.1 --port 8765" in combined
    assert "operator.app_factory" in combined
    assert "operator.static_ui" in combined
    assert "operator.approval_binding" in combined
    assert "hosted API" in operator_docs
    assert "Roadmap / Not implemented yet" in operator_docs


def test_release_package_check_builds_installs_and_records_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
            (dist / "agent_harness-9.9.9-py3-none-any.whl").write_text("wheel", encoding="utf-8")
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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")

    assert main(["template", "validate", "--all"]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["status"] == "passed"
    assert {entry["template_id"] for entry in evidence["templates"]} == {
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    }

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
                "[tool.setuptools.package-data]",
                "agent_harness = [",
                '  "operator/static/*.html",',
                '  "operator/static/*.css",',
                '  "operator/static/*.js",',
                "]",
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
    (docs / "migration.md").write_text(
        "\n".join(
            [
                "# Schema Migration",
                "",
                "## Migration Notes From v0.3.0 To v1.0.0",
                "",
                "v1.0.0 keeps the v0.3.0 V2 schemas as the public baseline.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (docs / "release-readiness.md").write_text(
        "\n".join(
            [
                "# Release Readiness",
                "",
                "## Release Checklist",
                "",
                "Run package, demo, template, docs, artifact, tag, and CI checks.",
                "",
                "## Tag Process",
                "",
                "Create and push the release tag only after final verification.",
                "",
                "## Artifact Verification",
                "",
                "Verify wheel and source distribution hashes before release.",
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
    (dist / f"agent_harness-{version}-py3-none-any.whl").write_text("wheel", encoding="utf-8")
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
        (evidence / f"{name}.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    retrieval_scorecards = root / ".agent-harness" / "retrieval-scorecards"
    retrieval_scorecards.mkdir(parents=True)
    (retrieval_scorecards / "quality-demo.json").write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard.v1",
                "status": "passed",
                "index_id": "quality-demo",
            }
        ),
        encoding="utf-8",
    )
    demo = root / "examples" / "retrieval_quality"
    (demo / "docs" / "public").mkdir(parents=True)
    (demo / "docs" / "internal").mkdir(parents=True)
    (demo / "expected").mkdir()
    for relative in (
        "README.md",
        "config.v2.yaml",
        "policy.v2.yaml",
        "scorecard.yaml",
        "task.json",
        "expected/retrieval_index.json",
        "expected/retrieval_scorecard.json",
        "docs/public/architecture.md",
        "docs/public/coding-rules.md",
        "docs/public/public-notes.md",
        "docs/public/semantic-note.md",
        "docs/internal/denied-internal.md",
        "docs/internal/secret-internal.md",
    ):
        path = demo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "config.v2.yaml":
            path.write_text(
                "\n".join(
                    [
                        "schema_version: config.v2",
                        "project_name: retrieval-quality-demo",
                        "artifact_root: .agent-harness",
                        "default_policy: default",
                        "retrieval_backend: lexical",
                        "template_catalog: bundled",
                        "retrieval:",
                        "  dense:",
                        "    embedding_backend: fastembed",
                        "    remote_embeddings: false",
                        "  qdrant:",
                        "    backend: qdrant-local",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        else:
            path.write_text("demo\n", encoding="utf-8")


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
