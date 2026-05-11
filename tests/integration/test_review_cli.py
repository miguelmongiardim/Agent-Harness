from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import agent_harness.review.run as review_run
from agent_harness.cli import main
from agent_harness.review.run import CommandExecutionResult
from tests.conftest import seed_project


def test_review_profiles_json_lists_builtin_catalog_without_writing_artifacts(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    before = _relative_files(tmp_path)

    assert main(["review", "profiles", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "review_profile_catalog.v1"
    profiles = {profile["profile_id"]: profile for profile in payload["profiles"]}
    assert list(profiles) == ["quick", "standard", "release"]

    quick = profiles["quick"]
    assert quick["expected_duration_class"] == "fast"
    assert [command["command"] for command in quick["commands"]] == [
        "agent-harness doctor",
        "agent-harness docs check",
        "python -m pytest -q",
    ]
    assert [command["required"] for command in quick["commands"]] == [True, True, True]
    assert {command["expected_duration_class"] for command in quick["commands"]} == {"fast"}
    assert all(command["evidence_expectations"] for command in quick["commands"])

    standard = profiles["standard"]
    assert standard["expected_duration_class"] == "moderate"
    assert [command["command_id"] for command in standard["commands"][:3]] == [
        command["command_id"] for command in quick["commands"]
    ]
    assert "ruff" in [command["command_id"] for command in standard["commands"]]
    assert "template_validate_all" in [command["command_id"] for command in standard["commands"]]

    release = profiles["release"]
    assert release["expected_duration_class"] == "release"
    release_prefix = release["commands"][: len(standard["commands"])]
    assert [command["command_id"] for command in release_prefix] == [
        command["command_id"] for command in standard["commands"]
    ]
    assert release["commands"][-1]["command"] == "agent-harness release readiness"
    assert release["commands"][-1]["required"] is True

    assert _relative_files(tmp_path) == before


def test_review_status_quick_reads_existing_evidence_without_running_checks(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs_report = tmp_path / ".agent-harness" / "docs" / "docs-check.json"
    docs_report.parent.mkdir(parents=True)
    docs_report.write_text(
        json.dumps(
            {
                "schema_version": "docs_check.v1",
                "status": "passed",
                "generated_at": "2026-05-11T10:00:00+00:00",
                "findings": [],
                "counts": {"findings": 0},
            }
        ),
        encoding="utf-8",
    )
    eval_report = tmp_path / ".agent-harness" / "evals" / "eval-20260511T100100Z.json"
    eval_report.parent.mkdir(parents=True)
    eval_report.write_text(
        json.dumps({"schema_version": "eval_scorecard.v1", "status": "passed"}),
        encoding="utf-8",
    )
    before = _relative_files(tmp_path)

    assert main(["review", "status", "--profile", "quick", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "review_status.v1"
    assert payload["profile_id"] == "quick"
    statuses = {command["command_id"]: command for command in payload["commands"]}
    assert statuses["docs_check"]["evidence_status"] == "present"
    assert statuses["docs_check"]["evidence_refs"] == [".agent-harness/docs/docs-check.json"]
    assert statuses["doctor"]["evidence_status"] == "missing"
    assert statuses["pytest_quick"]["evidence_status"] == "missing"
    assert {item["command_id"] for item in payload["missing_evidence"]} == {
        "doctor",
        "pytest_quick",
    }
    assert all(action["command"] for action in payload["next_actions"])
    assert _relative_files(tmp_path) == before
    assert not (tmp_path / ".agent-harness" / "release").exists()
    assert not (tmp_path / ".agent-harness" / "governance").exists()
    assert not (tmp_path / ".agent-harness" / "evidence").exists()
    assert not (tmp_path / ".agent-harness" / "runs").exists()


def test_review_run_quick_continues_after_failure_and_writes_safe_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-05-11T10:02:00Z")
    seed_project(tmp_path)
    attempted: list[list[str]] = []

    def fake_run_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> CommandExecutionResult:
        assert cwd == tmp_path
        assert timeout_seconds > 0
        attempted.append(argv)
        if argv == ["agent-harness", "docs", "check"]:
            return CommandExecutionResult(
                return_code=1,
                stdout="docs failed at C:\\Users\\mmarque9\\secret\\raw.txt",
                stderr="SECRET_TOKEN=sk-test must not persist",
                duration_seconds=0.2,
            )
        return CommandExecutionResult(
            return_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(review_run, "_run_command", fake_run_command)

    assert main(["review", "run", "--profile", "quick", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert attempted == [
        ["agent-harness", "doctor"],
        ["agent-harness", "docs", "check"],
        ["python", "-m", "pytest", "-q"],
    ]
    assert payload["schema_version"] == "review_run.v1"
    assert payload["profile_id"] == "quick"
    assert payload["status"] == "failed"
    results = {command["command_id"]: command for command in payload["commands"]}
    assert results["doctor"]["status"] == "passed"
    assert results["docs_check"]["status"] == "failed"
    assert results["pytest_quick"]["status"] == "passed"
    assert payload["artifact"].startswith(".agent-harness/review/review-run-")
    stored = json.loads((tmp_path / payload["artifact"]).read_text(encoding="utf-8"))
    assert stored == payload
    serialized = json.dumps(payload)
    assert "SECRET_TOKEN" not in serialized
    assert "sk-test" not in serialized
    assert "C:\\Users" not in serialized
    assert "[redacted" in serialized


def test_review_run_release_passes_ci_run_id_and_never_invokes_publish_actions(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    attempted: list[list[str]] = []

    def fake_run_command(
        argv: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> CommandExecutionResult:
        del cwd, timeout_seconds
        attempted.append(argv)
        return CommandExecutionResult(
            return_code=1 if argv == ["python", "-m", "mypy"] else 0,
            stdout="ok",
            stderr="",
            duration_seconds=0.1,
        )

    monkeypatch.setattr(review_run, "_run_command", fake_run_command)

    assert main(["review", "run", "--profile", "release", "--ci-run-id", "123", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)

    assert attempted[-1] == ["agent-harness", "release", "readiness", "--ci-run-id", "123"]
    command_ids = [command["command_id"] for command in payload["commands"]]
    assert command_ids[:3] == ["doctor", "docs_check", "pytest_quick"]
    assert "template_validate_all" in command_ids
    assert "package_check" in command_ids
    assert "evidence_pack" in command_ids
    assert command_ids[-1] == "release_readiness"
    assert payload["commands"][-1]["command"] == "agent-harness release readiness --ci-run-id 123"
    assert payload["commands"][-1]["status"] == "passed"
    assert payload["status"] == "failed"
    invoked = " ".join(" ".join(argv) for argv in attempted)
    assert " tag" not in invoked
    assert " push" not in invoked
    assert " publish" not in invoked
    assert " upload" not in invoked


def test_review_artifacts_writes_inventory_and_dry_run_cleanup_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-05-11T10:03:00Z")
    seed_project(tmp_path)
    old_timestamp = datetime(2026, 4, 20, tzinfo=UTC).timestamp()

    old_release_workspace = tmp_path / ".agent-harness" / "release" / "package-check-old"
    old_eval_workspace = tmp_path / ".agent-harness" / "eval-work" / "eval-old"
    for workspace in (old_release_workspace, old_eval_workspace):
        workspace.mkdir(parents=True)
        (workspace / "marker.txt").write_text("temporary\n", encoding="utf-8")
        os.utime(workspace / "marker.txt", (old_timestamp, old_timestamp))
        os.utime(workspace, (old_timestamp, old_timestamp))

    tracked_eval_workspace = tmp_path / ".agent-harness" / "eval-work" / "eval-tracked"
    tracked_eval_workspace.mkdir(parents=True)
    tracked_file = tracked_eval_workspace / "tracked.txt"
    tracked_file.write_text("tracked artifact\n", encoding="utf-8")
    os.utime(tracked_file, (old_timestamp, old_timestamp))
    os.utime(tracked_eval_workspace, (old_timestamp, old_timestamp))
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "add", "-f", ".agent-harness/eval-work/eval-tracked/tracked.txt"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    protected_paths = [
        tmp_path / ".agent-harness" / "runs" / "run-current" / "summary.json",
        tmp_path / ".agent-harness" / "runs" / "run-current" / "events.jsonl",
        tmp_path / ".agent-harness" / "release" / "evidence" / "package-build.json",
        tmp_path / ".agent-harness" / "evidence" / "evidence_pack.v1.json",
        tmp_path / ".agent-harness" / "governance" / "governance_summary.v1.json",
        tmp_path / "dist" / "agent_harness-1.9.1.tar.gz",
        tmp_path / "docs" / "source.md",
        tmp_path / "src" / "sample.py",
    ]
    for path in protected_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("protected\n", encoding="utf-8")

    assert main(["review", "artifacts", "--older-than-days", "7", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema_version"] == "review_artifacts.v1"
    inventory_path = tmp_path / payload["inventory_ref"]
    cleanup_path = tmp_path / payload["cleanup_plan_ref"]
    assert inventory_path.exists()
    assert cleanup_path.exists()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    cleanup = json.loads(cleanup_path.read_text(encoding="utf-8"))
    assert inventory["schema_version"] == "artifact_inventory.v1"
    assert cleanup["schema_version"] == "artifact_cleanup_plan.v1"
    assert cleanup["dry_run"] is True
    candidate_paths = {candidate["path"] for candidate in cleanup["candidates"]}
    assert candidate_paths == {
        ".agent-harness/eval-work/eval-old",
        ".agent-harness/release/package-check-old",
    }
    protected_inventory = {
        item["path"]: item for item in inventory["items"] if item["protected"] is True
    }
    for path in protected_paths:
        relative = path.relative_to(tmp_path).as_posix()
        assert relative in protected_inventory
    assert (
        protected_inventory[".agent-harness/eval-work/eval-tracked"]["protection_reason"]
        == "tracked files are protected"
    )
    for path in candidate_paths | set(protected_inventory):
        assert not Path(path).is_absolute()
        assert ".." not in Path(path).parts
    assert (old_release_workspace / "marker.txt").exists()
    assert (old_eval_workspace / "marker.txt").exists()
    assert tracked_file.exists()


def _relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
