from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import seed_project


def _artifact_path(root: Path, reference: str) -> Path:
    path = Path(reference)
    return path if path.is_absolute() else root / path


def test_cli_dry_run_creates_inspectable_run_artifacts(tmp_path: Path) -> None:
    seed_project(tmp_path)
    target = tmp_path / "sample.py"
    original = "def identity(value):\n    return value\n"
    target.write_text(original, encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "phase0-walking-skeleton",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-phase0"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["run_id"] == "run-phase0"
    assert summary["status"] == "dry_run"

    runs_dir = tmp_path / ".agent-harness" / "runs"
    assert [path.name for path in runs_dir.iterdir()] == ["run-phase0"]
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-phase0"
    checkpoint_index = json.loads((run_dir / "checkpoint-index.json").read_text(encoding="utf-8"))
    checkpoint_path = run_dir / "checkpoints" / f"{checkpoint_index['latest']}.json"
    required_artifacts = {
        "task": run_dir / "task.json",
        "policy": run_dir / "policy.json",
        "context_manifest": run_dir / "context_manifest.json",
        "events": run_dir / "events.jsonl",
        "checkpoint": checkpoint_path,
        "summary": run_dir / "summary.json",
    }
    assert set(required_artifacts).issubset(summary["artifacts"])
    for path in required_artifacts.values():
        assert path.exists(), path

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-phase0"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    assert inspected["summary"]["run_id"] == "run-phase0"
    event_types = [event["type"] for event in inspected["events"]]
    assert "run_started" in event_types
    assert "context_manifest_created" in event_types
    assert "checkpoint_created" in event_types
    assert "run_finished" in event_types
    assert target.read_text(encoding="utf-8") == original


def test_cli_dry_run_writes_artifact_index(tmp_path: Path) -> None:
    seed_project(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "phase0-artifact-index",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-artifact-index"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    run_dir = tmp_path / ".agent-harness" / "runs" / "run-artifact-index"
    artifact_index_path = run_dir / "artifact-index.json"

    assert _artifact_path(tmp_path, summary["artifacts"]["artifact_index"]).samefile(
        artifact_index_path
    )
    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    assert artifact_index["run_id"] == "run-artifact-index"
    assert _artifact_path(tmp_path, artifact_index["artifacts"]["summary"]).samefile(
        run_dir / "summary.json"
    )
    assert _artifact_path(tmp_path, artifact_index["artifacts"]["context_manifest"]).samefile(
        run_dir / "context_manifest.json"
    )


def test_cli_dry_run_records_context_policy_evidence(tmp_path: Path) -> None:
    seed_project(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "phase0-policy-evidence",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-policy-evidence"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr

    context = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "context", "run-policy-evidence"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert context.returncode == 0, context.stderr
    manifest = json.loads(context.stdout)
    source = manifest["sources"][0]
    assert source["path"] == "sample.py"
    assert source["policy_decision_id"]

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-policy-evidence"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    context_decisions = [
        event["payload"]["decision"]
        for event in inspected["events"]
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "context_source"
    ]
    assert context_decisions
    assert context_decisions[0]["decision_id"] == source["policy_decision_id"]
    assert context_decisions[0]["allowed"] is True


def test_inspect_run_returns_stored_artifact_index(tmp_path: Path) -> None:
    seed_project(tmp_path)
    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "phase0-inspect-artifacts",
                "title": "Inspect target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-inspect-artifacts"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-25T12:00:00Z"

    run = subprocess.run(
        [sys.executable, "-m", "agent_harness", "run", str(task_path), "--dry-run"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr

    inspect = subprocess.run(
        [sys.executable, "-m", "agent_harness", "inspect", "run", "run-inspect-artifacts"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    assert inspected["artifact_index"]["run_id"] == "run-inspect-artifacts"
    assert inspected["artifact_index"]["artifacts"] == inspected["summary"]["artifacts"]
