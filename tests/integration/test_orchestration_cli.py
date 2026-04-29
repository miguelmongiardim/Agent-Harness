from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_orchestration_run_help_is_discoverable(capsys) -> None:  # type: ignore[no-untyped-def]
    try:
        main(["orchestration", "run", "--help"])
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()
    assert "usage: agent-harness orchestration run" in captured.out
    assert "--dry-run" in captured.out
    assert "spec_path" in captured.out


def test_orchestration_run_denies_missing_policy_section_without_child_runs(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    spec_path = tmp_path / "orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "missing-policy",
                "title": "Missing policy section",
                "children": [
                    {
                        "child_id": "planner",
                        "role": "planner",
                        "title": "Plan",
                        "intent": "Plan without mutation.",
                        "target_paths": ["README.md"],
                        "allowed_tools": ["read_file"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 1
    captured = capsys.readouterr()
    assert "policy.v2.orchestration" in captured.err
    assert "missing" in captured.err
    assert not (tmp_path / ".agent-harness" / "runs").exists()
    assert not (tmp_path / ".agent-harness" / "orchestrations").exists()


def test_orchestration_run_reports_invalid_spec_before_policy_denial(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    spec_path = tmp_path / "invalid-orchestration.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "orchestration.v1",
                "orchestration_id": "invalid",
                "title": "Invalid",
            }
        ),
        encoding="utf-8",
    )

    assert main(["orchestration", "run", str(spec_path), "--dry-run"]) == 2
    captured = capsys.readouterr()
    assert "children" in captured.err
    assert "Field required" in captured.err
    assert "policy.v2.orchestration" not in captured.err
