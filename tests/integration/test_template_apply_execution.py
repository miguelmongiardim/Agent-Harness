from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from agent_harness.config.schema import HarnessConfig
from agent_harness.evals.schema import EvalSpec
from agent_harness.policy.schema import PolicyProfile
from agent_harness.tasks.schema import TaskSpec
from agent_harness.templates.schema import TemplateDetail
from tests.conftest import seed_project


def test_template_apply_clean_target_persists_application_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "template-clean-apply-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T16:00:00Z")

    target = tmp_path / "scaffold"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--target",
                str(target),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)

    assert summary["status"] == "completed"
    assert summary["approvals"] == []
    assert (target / "pyproject.toml").exists()
    assert (target / "src" / "example_python_lib" / "core.py").exists()
    assert {
        path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()
    } == {
        "README.md",
        "examples/agent-harness.config.json",
        "examples/default.policy.json",
        "examples/python-lib.eval.json",
        "examples/python-lib.task.json",
        "pyproject.toml",
        "src/example_python_lib/__init__.py",
        "src/example_python_lib/core.py",
        "tests/test_core.py",
    }

    evidence_path = tmp_path / summary["artifacts"]["template_application"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "template_application.v1"
    assert evidence["status"] == "completed"
    assert evidence["mode"] == "apply"
    assert evidence["template_id"] == "python-lib"
    assert evidence["template_version"] == "1.0.0"
    assert evidence["target_path"] == "scaffold"
    assert evidence["parameters"] == {"package_name": "example_python_lib"}
    assert evidence["planned_files"] == [
        "scaffold/README.md",
        "scaffold/pyproject.toml",
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
        "scaffold/examples/agent-harness.config.json",
        "scaffold/examples/default.policy.json",
        "scaffold/examples/python-lib.task.json",
        "scaffold/examples/python-lib.eval.json",
    ]
    assert evidence["created_files"] == evidence["planned_files"]
    assert set(evidence["operation_types"].values()) == {"create"}
    assert set(evidence["rendered_hashes"]) == set(evidence["planned_files"])
    assert evidence["plan_hash"]
    assert evidence["diagnostics"] == []
    assert evidence["policy_profile"] == "default"

    workspace = json.loads(
        (tmp_path / ".agent-harness" / "workspace.json").read_text(encoding="utf-8")
    )
    action_files = list(
        (tmp_path / ".agent-harness" / "runs" / "template-clean-apply-run" / "actions").glob(
            "*.json"
        )
    )
    action_id = action_files[0].stem
    assert workspace["applied_templates"] == [
        {
            "template_id": "python-lib",
            "version": "1.0.0",
            "destination": "scaffold",
            "run_id": "template-clean-apply-run",
            "action_id": action_id,
            "evidence": summary["artifacts"]["template_application"],
            "applied_at": "2026-04-28T16:00:00Z",
        }
    ]


def test_template_apply_clean_target_writes_valid_generated_examples(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    target = tmp_path / "scaffold"

    assert main(["template", "apply", "python-lib", "--target", str(target)]) == 0
    capsys.readouterr()

    config = target / "examples" / "agent-harness.config.json"
    policy = target / "examples" / "default.policy.json"
    task = target / "examples" / "python-lib.task.json"
    eval_spec = target / "examples" / "python-lib.eval.json"

    HarnessConfig.model_validate_json(config.read_text(encoding="utf-8"))
    PolicyProfile.model_validate_json(policy.read_text(encoding="utf-8"))
    TaskSpec.model_validate_json(task.read_text(encoding="utf-8"))
    EvalSpec.model_validate_json(eval_spec.read_text(encoding="utf-8"))


def test_template_apply_failure_rolls_back_created_files_and_records_failed_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "template-write-failure-run")
    template = TemplateDetail(
        template_id="write-failure",
        version="1.0.0",
        title="Write Failure",
        description="Synthetic clean-apply failure fixture.",
        bundle_path="bundled_templates/write-failure.json",
        files=[
            {"path": "blocked", "content": "created first\n"},
            {"path": "blocked/child.txt", "content": "cannot create below a file\n"},
        ],
    )
    monkeypatch.setattr("agent_harness.cli.load_template", lambda name, root=None: template)
    monkeypatch.setattr(
        "agent_harness.core.runtime.load_template",
        lambda name, root=None: template,
    )

    assert (
        main(
            [
                "template",
                "apply",
                "write-failure",
                "--target",
                str(tmp_path / "scaffold"),
            ]
        )
        == 1
    )
    capsys.readouterr()

    assert not (tmp_path / "scaffold" / "blocked").exists()
    assert not (tmp_path / ".agent-harness" / "workspace.json").exists()

    evidence_path = (
        tmp_path / ".agent-harness" / "template_applications" / "template-write-failure-run.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "template_application.v1"
    assert evidence["status"] == "failed"
    assert evidence["created_files"] == []
    assert evidence["rolled_back_files"] == ["scaffold/blocked"]
    assert evidence["failure"]["path"] == "scaffold/blocked/child.txt"


def test_template_apply_rejects_undeclared_parameters_before_writing(
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
                "--param",
                "unknown=value",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "undeclared template parameter: unknown" in captured.err
    assert not (target / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_rejects_invalid_bundled_pack_before_writing(
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
    monkeypatch.setattr("agent_harness.cli.load_template", lambda name, root=None: template)
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
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "template pack validation failed" in captured.err
    assert captured.out == ""
    assert not (tmp_path / "scaffold" / ".hidden").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_rejects_target_outside_project_before_writing(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside-scaffold"

    assert main(["template", "apply", "python-lib", "--target", str(outside)]) == 1
    captured = capsys.readouterr()

    assert "template destination outside project root" in captured.err
    assert not (outside / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness").exists()


def test_template_apply_rejects_symlink_target_escape_before_writing(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside-symlink-target"
    outside.mkdir()
    link = tmp_path / "linked-scaffold"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    assert main(["template", "apply", "python-lib", "--target", str(link)]) == 1
    captured = capsys.readouterr()

    assert "template destination outside project root" in captured.err
    assert not (outside / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness").exists()
