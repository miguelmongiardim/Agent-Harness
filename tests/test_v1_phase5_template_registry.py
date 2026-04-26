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


def test_template_apply_is_approval_bound_and_records_applied_version(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "phase5-template-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T14:00:00Z")

    destination = tmp_path / "scaffold"

    assert main(["template", "apply", "python-lib", "--destination", str(destination)]) == 0
    proposed = json.loads(capsys.readouterr().out)

    assert proposed["run_id"] == "phase5-template-run"
    assert proposed["status"] == "paused"
    assert proposed["approvals"]
    assert not (destination / "pyproject.toml").exists()

    run_dir = tmp_path / ".agent-harness" / "runs" / "phase5-template-run"
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
                "phase5-template-run",
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
            "run_id": "phase5-template-run",
            "action_id": action_id,
            "applied_at": "2026-04-26T14:00:00Z",
        }
    ]
