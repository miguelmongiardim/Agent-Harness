from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from tests.conftest import seed_project


def _write_read_only_task(root: Path, task_id: str) -> Path:
    target = root / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": task_id,
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    return task_path


def _run_fixed_seed_dry_run(root: Path, task_path: Path, run_id: str) -> dict[str, object]:
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = run_id
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"
    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_sqlite_audit_rows_match_jsonl_events_and_summary(tmp_path: Path) -> None:
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "phase2-audit-consistency")

    _run_fixed_seed_dry_run(tmp_path, task_path, "run-audit-consistency")
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-audit-consistency"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    event_lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]

    with sqlite3.connect(tmp_path / ".agent-harness" / "state.sqlite3") as conn:
        run_row = conn.execute(
            """
            select task_id, status, summary_path, events_count
            from runs
            where run_id = ?
            """,
            ("run-audit-consistency",),
        ).fetchone()
        event_rows = conn.execute(
            """
            select sequence, event_id, run_id, type, event_hash
            from events
            where run_id = ?
            order by sequence
            """,
            ("run-audit-consistency",),
        ).fetchall()

    assert run_row is not None
    task_id, status, summary_path, events_count = run_row
    assert task_id == "phase2-audit-consistency"
    assert status == "dry_run"
    stored_summary_path = Path(summary_path)
    if not stored_summary_path.is_absolute():
        stored_summary_path = tmp_path / ".agent-harness" / stored_summary_path
    assert stored_summary_path.samefile(run_dir / "summary.json")
    assert events_count == summary["events_count"]
    assert summary["events_count"] == len(events)
    assert len(event_rows) == len(events)
    for index, (sequence, event_id, run_id, event_type, event_hash) in enumerate(
        event_rows, start=1
    ):
        event = events[index - 1]
        assert sequence == index
        assert event_id == event["event_id"]
        assert run_id == event["run_id"]
        assert event_type == event["type"]
        assert event_hash == hashlib.sha256(event_lines[index - 1].encode("utf-8")).hexdigest()


def test_fixed_seed_dry_runs_write_stable_artifact_hashes(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    seed_project(first_root)
    seed_project(second_root)
    first_task = _write_read_only_task(first_root, "phase2-reproducible")
    second_task = _write_read_only_task(second_root, "phase2-reproducible")

    first_summary = _run_fixed_seed_dry_run(first_root, first_task, "run-reproducible")
    second_summary = _run_fixed_seed_dry_run(second_root, second_task, "run-reproducible")
    first_index = json.loads(
        (first_root / ".agent-harness" / "runs" / "run-reproducible" / "artifact-index.json")
        .read_text(encoding="utf-8")
    )
    second_index = json.loads(
        (second_root / ".agent-harness" / "runs" / "run-reproducible" / "artifact-index.json")
        .read_text(encoding="utf-8")
    )

    stable_summary_fields = ["run_id", "task_id", "status", "events_count", "message"]
    assert {field: first_summary[field] for field in stable_summary_fields} == {
        field: second_summary[field] for field in stable_summary_fields
    }
    assert all(not Path(path).is_absolute() for path in first_index["artifacts"].values())
    assert first_index["artifacts"] == second_index["artifacts"]

    required_hashed_artifacts = {
        "task",
        "policy",
        "context_manifest",
        "events",
        "checkpoint",
        "checkpoint_index",
        "summary",
    }
    assert required_hashed_artifacts.issubset(first_index["artifact_hashes"])
    assert first_index["artifact_hashes"] == second_index["artifact_hashes"]
    for name in required_hashed_artifacts:
        artifact_path = first_root / first_index["artifacts"][name]
        assert artifact_path.exists(), name
        assert first_index["artifact_hashes"][name] == hashlib.sha256(
            artifact_path.read_bytes()
        ).hexdigest()


def test_reusing_fixed_run_id_is_rejected_without_changing_existing_audit_log(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "phase2-duplicate-run")

    _run_fixed_seed_dry_run(tmp_path, task_path, "run-duplicate")
    events_path = tmp_path / ".agent-harness" / "runs" / "run-duplicate" / "events.jsonl"
    original_events = events_path.read_text(encoding="utf-8")
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-duplicate"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    rerun = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert rerun.returncode == 1
    assert "run already exists: run-duplicate" in rerun.stderr
    assert events_path.read_text(encoding="utf-8") == original_events


def test_checkpoint_hash_includes_prior_event_evidence(tmp_path: Path) -> None:
    seed_project(tmp_path)
    task_path = _write_read_only_task(tmp_path, "phase2-checkpoint-evidence")

    _run_fixed_seed_dry_run(tmp_path, task_path, "run-checkpoint-evidence")
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-checkpoint-evidence"
    checkpoint_index = json.loads((run_dir / "checkpoint-index.json").read_text(encoding="utf-8"))
    checkpoint = json.loads(
        (run_dir / "checkpoints" / f"{checkpoint_index['latest']}.json").read_text(
            encoding="utf-8"
        )
    )
    event_lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    checkpoint_event_index = next(
        index for index, event in enumerate(events) if event["type"] == "checkpoint_created"
    )
    prior_event_log = "".join(f"{line}\n" for line in event_lines[:checkpoint_event_index])

    assert checkpoint["previous_event_hash"] == hashlib.sha256(
        prior_event_log.encode("utf-8")
    ).hexdigest()
    assert events[checkpoint_event_index]["payload"]["checkpoint_hash"]
