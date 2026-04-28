from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agent_harness.cli import main
from agent_harness.utils import sha256_json
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
    assert template["bundle_path"] == "bundled_templates/python-lib/template.v2.toml"
    assert template["source_type"] == "bundled_pack"
    assert template["compatibility_status"] == "compatible"
    assert template["files"]


def test_template_list_fails_clearly_on_duplicate_registry_ids(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    registry = tmp_path / "registry.sqlite3"
    with sqlite3.connect(registry) as conn:
        conn.execute(
            """
            create table template_registry (
              template_id text,
              version text,
              title text,
              description text,
              bundle_path text,
              tags_json text
            )
            """
        )
        rows = [
            (
                "python-lib",
                "1.0.0",
                "Python Library",
                "First record",
                "bundled_templates/python-lib.json",
                "[]",
            ),
            (
                "python-lib",
                "1.0.0",
                "Python Library Duplicate",
                "Second record",
                "bundled_templates/python-lib.json",
                "[]",
            ),
        ]
        conn.executemany("insert into template_registry values (?, ?, ?, ?, ?, ?)", rows)

    @contextmanager
    def fake_registry_path() -> Iterator[Path]:
        yield registry

    monkeypatch.setattr("agent_harness.templates.registry.registry_path", fake_registry_path)

    assert main(["template", "list"]) == 1
    result = capsys.readouterr()
    assert "duplicate template ids discovered: python-lib" in result.err


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
    (destination / "NOTES.md").write_text("# Existing workspace\n", encoding="utf-8")

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
    assert len(action["proposed_writes"]) == 9
    assert {entry["path"] for entry in action["proposed_writes"]} == {
        "scaffold/README.md",
        "scaffold/examples/agent-harness.config.json",
        "scaffold/examples/default.policy.json",
        "scaffold/examples/python-lib.eval.json",
        "scaffold/examples/python-lib.task.json",
        "scaffold/pyproject.toml",
        "scaffold/src/example_python_lib/__init__.py",
        "scaffold/src/example_python_lib/core.py",
        "scaffold/tests/test_core.py",
    }
    planned_files = [entry["path"] for entry in action["proposed_writes"]]
    operation_types = {path: "create" for path in planned_files}
    rendered_hashes = {
        entry["path"]: entry["after_hash"] for entry in action["proposed_writes"]
    }
    plan_payload = {
        "template_id": "python-lib",
        "template_version": "1.0.0",
        "target_path": "scaffold",
        "planned_files": planned_files,
        "operation_types": operation_types,
        "rendered_hashes": rendered_hashes,
    }
    assert action["approval_binding"] == {
        **plan_payload,
        "plan_hash": sha256_json(plan_payload),
        "policy_profile": "default",
        "checkpoint_hash": action["checkpoint_hash"],
    }

    approval = json.loads(
        (run_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8")
    )
    assert approval["policy_profile"] == action["approval_binding"]["policy_profile"]
    assert approval["checkpoint_hash"] == action["approval_binding"]["checkpoint_hash"]

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
            "evidence": "",
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
    pyproject = destination / "pyproject.toml"
    assert pyproject.exists()
    original_pyproject = pyproject.read_text(encoding="utf-8")

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
    assert pyproject.read_text(encoding="utf-8") == original_pyproject

    run_dir = tmp_path / ".agent-harness" / "runs" / "template-overwrite-run"
    action_id = overwrite["approvals"][0]
    action = json.loads((run_dir / "actions" / f"{action_id}.json").read_text(encoding="utf-8"))
    assert set(action["approval_binding"]["operation_types"].values()) == {"overwrite"}
