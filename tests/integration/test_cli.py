from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from tests.conftest import seed_project


def test_cli_init_creates_project_foundation_and_honest_starter_docs(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    assert (tmp_path / "agent-harness.yaml").exists()
    assert (tmp_path / "policies" / "default.json").exists()
    assert (tmp_path / ".agent-harness" / "runs").is_dir()
    assert (tmp_path / ".agent-harness" / "indexes").is_dir()

    starter_doc = tmp_path / "docs" / "agent-harness.md"
    assert starter_doc.exists()
    text = starter_doc.read_text(encoding="utf-8")
    assert "## Implemented Locally" in text
    assert "## Roadmap / Not Enabled By Init" in text
    assert "enterprise-ready" not in text.lower()


def test_cli_init_is_idempotent_unless_forced(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    config = tmp_path / "agent-harness.yaml"
    policy = tmp_path / "policies" / "default.json"
    starter_doc = tmp_path / "docs" / "agent-harness.md"
    config.write_text("custom config\n", encoding="utf-8")
    policy.write_text('{"custom": true}\n', encoding="utf-8")
    starter_doc.write_text("custom docs\n", encoding="utf-8")

    assert main(["init"]) == 0
    assert config.read_text(encoding="utf-8") == "custom config\n"
    assert policy.read_text(encoding="utf-8") == '{"custom": true}\n'
    assert starter_doc.read_text(encoding="utf-8") == "custom docs\n"

    assert main(["init", "--force"]) == 0
    assert "schema_version: config.v1" in config.read_text(encoding="utf-8")
    assert '"schema_version": "policy.v1"' in policy.read_text(encoding="utf-8")
    assert "## Implemented Locally" in starter_doc.read_text(encoding="utf-8")


def test_cli_template_apply(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    capsys.readouterr()

    destination = tmp_path / "scratch"
    assert main(["template", "apply", "python-lib", "--destination", str(destination)]) == 0
    proposed = json.loads(capsys.readouterr().out)
    assert proposed["status"] == "paused"
    assert proposed["approvals"]
    assert not (destination / "pyproject.toml").exists()

    assert (
        main(
            [
                "approve",
                proposed["run_id"],
                proposed["approvals"][0],
                "--decision",
                "approve",
                "--actor",
                "reviewer",
            ]
        )
        == 0
    )
    assert (destination / "pyproject.toml").exists()
    assert (destination / "src" / "example_python_lib" / "core.py").exists()


def test_cli_template_list_and_show_python_lib(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["template", "list"]) == 0
    listed = capsys.readouterr()
    assert any(
        line.startswith("python-lib\t1.0.0\tPython Library")
        for line in listed.out.splitlines()
    )

    assert main(["template", "show", "python-lib"]) == 0
    shown = capsys.readouterr()
    template = json.loads(shown.out)
    assert template["template_id"] == "python-lib"
    assert template["version"] == "1.0.0"
    assert template["files"]


def test_cli_commit_propose_records_pending_git_commit_approval(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    target = tmp_path / "fixture.py"
    target.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "cli-git-commit",
                "title": "Refactor",
                "intent": "Refactor add_numbers",
                "target_paths": ["fixture.py"],
                "allowed_tools": ["read_file", "patch_file", "git_commit"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "agent-harness@example.test")
    _git(tmp_path, "config", "user.name", "Agent Harness Test")
    _git(tmp_path, "add", "agent-harness.yaml", "policies/default.json", "fixture.py", "task.json")
    _git(tmp_path, "commit", "-m", "initial")

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-cli-git-commit")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T20:15:00Z")
    assert main(["run", str(task_path)]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    assert run_summary["status"] == "paused"

    assert (
        main(
            [
                "approve",
                run_summary["run_id"],
                run_summary["approvals"][0],
                "--decision",
                "approve",
                "--actor",
                "reviewer",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "commit",
                "propose",
                run_summary["run_id"],
                "--message",
                "refactor fixture addition",
            ]
        )
        == 0
    )
    commit_summary = json.loads(capsys.readouterr().out)
    commit_action_id = commit_summary["approvals"][-1]
    assert commit_summary["status"] == "paused"

    planned = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / run_summary["run_id"]
            / "git_commit.json"
        ).read_text(encoding="utf-8")
    )
    assert planned["action_id"] == commit_action_id
    assert planned["file_set"] == ["fixture.py"]


def test_cli_template_apply_respects_policy_write_roots(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    capsys.readouterr()
    limited_policy = dict(DEFAULT_POLICY)
    limited_policy["name"] = "limited"
    limited_policy["write_roots"] = ["allowed"]
    (tmp_path / "policies" / "limited.json").write_text(
        json.dumps(limited_policy, indent=2), encoding="utf-8"
    )

    allowed = tmp_path / "allowed"
    blocked = tmp_path / "blocked"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--destination",
                str(allowed),
                "--profile",
                "limited",
            ]
        )
        == 0
    )
    proposed = json.loads(capsys.readouterr().out)
    assert proposed["status"] == "paused"
    assert (
        main(
            [
                "approve",
                proposed["run_id"],
                proposed["approvals"][0],
                "--decision",
                "approve",
                "--actor",
                "reviewer",
            ]
        )
        == 0
    )
    assert (allowed / "pyproject.toml").exists()

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--destination",
                str(blocked),
                "--profile",
                "limited",
            ]
        )
        == 1
    )
    assert not (blocked / "pyproject.toml").exists()


def test_cli_eval_fails_when_docs_claim_unsupported_behavior(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "claim.md").write_text(
        "# Claim\n\nAgent Harness provides a web API.\n", encoding="utf-8"
    )
    target = tmp_path / "fixtures" / "python_refactor" / "legacy_math.py"
    target.parent.mkdir(parents=True)
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task = tmp_path / "examples" / "tasks" / "python_refactor.json"
    task.parent.mkdir(parents=True)
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "docs-honesty",
                "title": "Inspect fixture",
                "intent": "Inspect fixture without mutation.",
                "target_paths": ["fixtures/python_refactor/legacy_math.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )

    assert main(["eval"]) == 1
    scanner = json.loads(
        (tmp_path / ".agent-harness" / "exports" / "scanner-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert scanner["status"] == "failed"
    assert scanner["critical_findings"][0]["rule_id"] == "unsupported_doc_claim"


def test_cli_task_validate_returns_concrete_errors(
    tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    invalid_task = tmp_path / "invalid-task.json"
    invalid_task.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "invalid",
                "intent": "Missing title should fail validation.",
            }
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(invalid_task)]) == 2
    captured = capsys.readouterr()
    assert "title" in captured.err
    assert "Field required" in captured.err


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip()
