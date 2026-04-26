from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import seed_project


def test_cli_langgraph_runtime_emits_native_policy_and_audit_evidence(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)
    langgraph_package = tmp_path / "langgraph"
    langgraph_package.mkdir()
    (langgraph_package / "__init__.py").write_text("__version__ = '0.0-test'\n", encoding="utf-8")

    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "langgraph-boundary-proof",
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
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "run-langgraph-boundary"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T22:00:00Z"

    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "run",
            str(task_path),
            "--runtime",
            "langgraph",
            "--dry-run",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    summary = json.loads(run.stdout)
    assert summary["status"] == "dry_run"
    assert summary["artifacts"]["runtime_adapter"].endswith("runtime_adapter.json")
    assert summary["artifacts"]["context_manifest"].endswith("context_manifest.json")
    assert summary["artifacts"]["events"].endswith("events.jsonl")
    assert summary["artifacts"]["policy"].endswith("policy.json")

    inspect = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_harness",
            "inspect",
            "run",
            "run-langgraph-boundary",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert inspect.returncode == 0, inspect.stderr
    inspected = json.loads(inspect.stdout)
    runtime_adapter = inspected["runtime_adapter"]
    assert runtime_adapter["adapter_id"] == "langgraph"
    assert runtime_adapter["execution_boundary"] == "native_runtime_delegate"
    assert runtime_adapter["package"] == "langgraph"
    assert runtime_adapter["package_present"] is True

    event_types = [event["type"] for event in inspected["events"]]
    assert "runtime_adapter_selected" in event_types
    assert "security_scan_completed" in event_types
    assert "context_manifest_created" in event_types
    assert "policy_decision" in event_types
    assert "tool_observation" in event_types
    assert inspected["artifact_index"]["artifacts"]["runtime_adapter"].endswith(
        "runtime_adapter.json"
    )
