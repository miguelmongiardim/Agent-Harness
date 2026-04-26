from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_template_list_and_show_use_packaged_registry_metadata(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["template", "list"]) == 0
    listed = capsys.readouterr()
    lines = listed.out.splitlines()
    assert any(line.startswith("python-lib\t1.0.0\tPython Library") for line in lines)

    assert main(["template", "show", "python-lib"]) == 0
    shown = capsys.readouterr()
    template = json.loads(shown.out)

    assert template["template_id"] == "python-lib"
    assert template["version"] == "1.0.0"
    assert template["title"] == "Python Library"
    assert template["bundle_path"] == "bundled_templates/python-lib.json"
    assert template["files"]


def test_template_apply_to_non_empty_destination_is_approval_bound_and_records_version(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "template-apply-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T14:00:00Z")

    destination = tmp_path / "scaffold"
    destination.mkdir()
    (destination / "README.md").write_text("# Existing workspace\n", encoding="utf-8")

    assert main(["template", "apply", "python-lib", "--destination", str(destination)]) == 0
    proposed = json.loads(capsys.readouterr().out)

    assert proposed["run_id"] == "template-apply-run"
    assert proposed["status"] == "paused"
    assert proposed["approvals"]
    assert not (destination / "pyproject.toml").exists()

    run_dir = tmp_path / ".agent-harness" / "runs" / "template-apply-run"
    action_id = proposed["approvals"][0]
    action = json.loads((run_dir / "actions" / f"{action_id}.json").read_text(encoding="utf-8"))

    assert action["kind"] == "template_apply"
    assert action["template"]["template_id"] == "python-lib"
    assert action["template"]["version"] == "1.0.0"
    assert len(action["proposed_writes"]) == 4
    assert {entry["path"] for entry in action["proposed_writes"]} == {
        "scaffold/pyproject.toml",
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
    }

    assert (
        main(
            [
                "approve",
                "template-apply-run",
                action_id,
                "--decision",
                "approve",
                "--actor",
                "reviewer",
            ]
        )
        == 0
    )

    assert (destination / "pyproject.toml").exists()
    workspace = json.loads(
        (tmp_path / ".agent-harness" / "workspace.json").read_text(encoding="utf-8")
    )
    assert workspace["applied_templates"] == [
        {
            "template_id": "python-lib",
            "version": "1.0.0",
            "destination": "scaffold",
            "run_id": "template-apply-run",
            "action_id": action_id,
            "applied_at": "2026-04-26T14:00:00Z",
        }
    ]


def test_template_apply_overwrite_with_force_remains_approval_bound(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "scaffold"

    assert main(["template", "apply", "python-lib", "--destination", str(destination)]) == 0
    clean = json.loads(capsys.readouterr().out)
    assert clean["status"] == "completed"
    assert (destination / "pyproject.toml").exists()

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "template-overwrite-run")
    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--destination",
                str(destination),
                "--force",
            ]
        )
        == 0
    )
    overwrite = json.loads(capsys.readouterr().out)

    assert overwrite["run_id"] == "template-overwrite-run"
    assert overwrite["status"] == "paused"
    assert overwrite["approvals"]
