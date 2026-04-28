from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.schemas import TemplateDetail
from tests.conftest import seed_project


def test_template_apply_dry_run_reports_plan_without_mutation(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    target = tmp_path / "scaffold"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--target",
                str(target),
                "--dry-run",
                "--param",
                "package_name=planned_lib",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)

    assert evidence["schema_version"] == "template_application.v1"
    assert evidence["status"] == "planned"
    assert evidence["mode"] == "dry_run"
    assert evidence["template_id"] == "python-lib"
    assert evidence["template_version"] == "1.0.0"
    assert evidence["source"]["source_type"] == "bundled_pack"
    assert evidence["target_path"] == "scaffold"
    assert evidence["parameters"] == {"package_name": "planned_lib"}
    assert evidence["planned_creates"] == [
        "scaffold/pyproject.toml",
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
    ]
    assert evidence["skipped_files"] == []
    assert evidence["conflicts"] == []
    assert evidence["generated_schema_versions"]["template"] == "template.v2"
    assert evidence["required_capabilities"] == ["python.library"]
    assert evidence["generated_files"] == [
        "pyproject.toml",
        "src/example_python_lib/__init__.py",
        "src/example_python_lib/core.py",
        "tests/test_core.py",
    ]
    assert evidence["plan_hash"]
    assert evidence["approval_required"] is False
    assert evidence["policy_profile"] == "default"
    assert evidence["diagnostics"] == []

    assert not (target / "pyproject.toml").exists()
    assert not (target / "src" / "example_python_lib" / "core.py").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_preview_diff_reports_relative_diffs_without_mutation(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    target = tmp_path / "scaffold"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--target",
                str(target),
                "--preview-diff",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)

    assert evidence["schema_version"] == "template_application.v1"
    assert evidence["status"] == "planned"
    assert evidence["mode"] == "preview_diff"
    assert evidence["target_path"] == "scaffold"
    assert evidence["parameters"] == {"package_name": "example_python_lib"}
    assert [entry["path"] for entry in evidence["preview_diffs"]] == [
        "scaffold/pyproject.toml",
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
    ]
    first_diff = evidence["preview_diffs"][0]["diff"]
    assert "--- a/scaffold/pyproject.toml" in first_diff
    assert "+++ b/scaffold/pyproject.toml" in first_diff
    assert str(tmp_path) not in first_diff

    assert not (target / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_dry_run_reports_conflicts_without_artifacts(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    target = tmp_path / "scaffold"
    target.mkdir()
    existing = target / "pyproject.toml"
    existing.write_text("[project]\nname = \"already-here\"\n", encoding="utf-8")

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--target",
                str(target),
                "--dry-run",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)

    assert evidence["status"] == "planned"
    assert evidence["planned_creates"] == [
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
    ]
    assert [conflict["path"] for conflict in evidence["conflicts"]] == [
        "scaffold/pyproject.toml"
    ]
    assert evidence["operation_types"]["scaffold/pyproject.toml"] == "conflict"
    assert evidence["approval_required"] is True

    assert existing.read_text(encoding="utf-8") == "[project]\nname = \"already-here\"\n"
    assert not (target / "src" / "example_python_lib" / "core.py").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_preview_diff_redacts_secret_like_values(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    template = TemplateDetail(
        template_id="redaction-check",
        version="1.0.0",
        title="Redaction Check",
        description="Synthetic template used to verify preview redaction.",
        bundle_path="bundled_templates/redaction-check.json",
        files=[
            {
                "path": "config.txt",
                "content": "API_TOKEN=super-secret-value\n",
            }
        ],
    )
    monkeypatch.setattr("agent_harness.cli.load_template", lambda name: template)

    assert (
        main(
            [
                "template",
                "apply",
                "redaction-check",
                "--target",
                str(tmp_path / "scaffold"),
                "--preview-diff",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)
    diff = evidence["preview_diffs"][0]["diff"]

    assert "super-secret-value" not in diff
    assert "[REDACTED]" in diff
    assert not (tmp_path / "scaffold" / "config.txt").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_destination_alias_repeated_params_and_existing_metadata_stay_untouched(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    artifact_root = tmp_path / ".agent-harness"
    artifact_root.mkdir()
    workspace = artifact_root / "workspace.json"
    original_workspace = (
        '{\n  "schema_version": "workspace_metadata.v1",\n  "applied_templates": []\n}\n'
    )
    workspace.write_text(original_workspace, encoding="utf-8")

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--destination",
                str(tmp_path / "scaffold"),
                "--dry-run",
                "--param",
                "package_name=first_lib",
                "--param",
                "package_name=second_lib",
            ]
        )
        == 0
    )
    evidence = json.loads(capsys.readouterr().out)

    assert evidence["target_path"] == "scaffold"
    assert evidence["parameters"] == {"package_name": "second_lib"}
    assert workspace.read_text(encoding="utf-8") == original_workspace
    assert not (artifact_root / "runs").exists()
    assert not (artifact_root / "template_applications").exists()
    assert not (tmp_path / "scaffold" / "pyproject.toml").exists()


def test_template_apply_preview_denies_target_escape_before_diff_output(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside-scaffold"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--target",
                str(outside),
                "--preview-diff",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "template destination outside project root" in captured.err
    assert captured.out == ""
    assert not (outside / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_preview_denies_invalid_pack_before_diff_output(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    template = TemplateDetail(
        template_id="hidden-output",
        version="1.0.0",
        title="Hidden Output",
        description="Synthetic invalid bundled pack.",
        bundle_path="bundled_templates/hidden-output/template.v2.toml",
        source_type="bundled_pack",
        files=[{"path": ".hidden", "content": "hidden\n"}],
    )
    monkeypatch.setattr("agent_harness.cli.load_template", lambda name: template)
    monkeypatch.setattr(
        "agent_harness.cli.validate_bundled_template_pack",
        lambda template_id: {
            "schema_version": "template_pack_validation.v1",
            "status": "failed",
            "diagnostics": [
                {
                    "rule_id": "hidden_generated_file",
                    "severity": "error",
                    "message": "hidden generated files are denied",
                    "location": "files[0].path",
                }
            ],
        },
    )

    assert (
        main(
            [
                "template",
                "apply",
                "hidden-output",
                "--target",
                str(tmp_path / "scaffold"),
                "--preview-diff",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "template pack validation failed" in captured.err
    assert captured.out == ""
    assert not (tmp_path / "scaffold" / ".hidden").exists()
    assert not (tmp_path / ".agent-harness").exists()
