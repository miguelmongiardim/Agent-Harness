from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness import release


def test_remote_ci_evidence_records_required_compatibility_jobs(
    monkeypatch,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    def fake_github_run(
        project_root: Path,
        target_commit: str,
        ci_run_id: str | None,
    ) -> dict[str, Any]:
        assert project_root == tmp_path
        assert target_commit == "abc123"
        assert ci_run_id == "24962697751"
        return {
            "databaseId": 24962697751,
            "url": "https://github.example/actions/runs/24962697751",
            "headSha": "abc123",
            "status": "completed",
            "conclusion": "success",
            "jobs": [
                {
                    "name": "compatibility (3.11)",
                    "conclusion": "success",
                    "url": "https://github.example/job/311",
                },
                {
                    "name": "compatibility (3.12)",
                    "conclusion": "success",
                    "url": "https://github.example/job/312",
                },
                {
                    "name": "compatibility (3.13)",
                    "conclusion": "failure",
                    "url": "https://github.example/job/313",
                },
            ],
        }

    monkeypatch.setattr(release, "_github_run", fake_github_run)

    evidence = release._remote_ci_evidence(tmp_path, "abc123", "24962697751")

    assert evidence["run"]["matches_target_commit"] is True
    assert evidence["python_3_11"]["status"] == "passed"
    assert evidence["python_3_12"]["status"] == "passed"
    assert evidence["python_3_13"]["status"] == "failed_allowed"
    assert release._required_remote_ci_passed(evidence) is True


def test_remote_ci_evidence_rejects_wrong_commit(
    monkeypatch,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    def fake_github_run(
        project_root: Path,
        target_commit: str,
        ci_run_id: str | None,
    ) -> dict[str, Any]:
        return {
            "databaseId": 1,
            "url": "https://github.example/actions/runs/1",
            "headSha": "different",
            "status": "completed",
            "conclusion": "success",
            "jobs": [
                {"name": "compatibility (3.11)", "conclusion": "success"},
                {"name": "compatibility (3.12)", "conclusion": "success"},
            ],
        }

    monkeypatch.setattr(release, "_github_run", fake_github_run)

    evidence = release._remote_ci_evidence(tmp_path, "abc123", "1")

    assert evidence["run"]["matches_target_commit"] is False
    assert evidence["python_3_11"]["status"] == "not_recorded"
    assert release._required_remote_ci_passed(evidence) is False
