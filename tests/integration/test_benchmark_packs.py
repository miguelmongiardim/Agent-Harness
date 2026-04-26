from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_cli_benchmark_run_imports_swebench_style_sample_into_evidence_backed_result(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["benchmark", "list"]) == 0
    listed = capsys.readouterr().out
    assert "local-samples\t1.0.0\tLocal Benchmark Samples" in listed

    assert main(["benchmark", "show", "local-samples"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["pack_id"] == "local-samples"
    assert {case["case_id"] for case in shown["cases"]} >= {
        "swebench-python-refactor",
        "terminal-readonly-inspect",
    }

    assert main(["benchmark", "run", "local-samples", "swebench-python-refactor"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "benchmark_result.v1"
    assert result["pack_id"] == "local-samples"
    assert result["case_id"] == "swebench-python-refactor"
    assert result["benchmark_kind"] == "swe_bench_style"
    assert result["status"] == "completed"
    assert result["passed"] is True
    assert result["approval_ids"]

    result_artifact = tmp_path / result["result_artifact"]
    exported_run = tmp_path / result["run_export"]
    assert result_artifact.exists()
    assert exported_run.exists()

    stored_result = json.loads(result_artifact.read_text(encoding="utf-8"))
    exported = json.loads(exported_run.read_text(encoding="utf-8"))
    assert stored_result == result
    assert exported["run_id"] == result["run_id"]
    assert exported["summary"]["status"] == "completed"
    assert any(event["type"] == "approval_decided" for event in exported["events"])
    assert any(event["type"] == "tool_observation" for event in exported["events"])


def test_cli_benchmark_run_imports_terminal_task_sample_without_synthetic_export(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["benchmark", "run", "local-samples", "terminal-readonly-inspect"]) == 0
    result = json.loads(capsys.readouterr().out)
    exported = json.loads((tmp_path / result["run_export"]).read_text(encoding="utf-8"))

    assert result["benchmark_kind"] == "terminal_task"
    assert result["status"] == "completed"
    assert result["passed"] is True
    assert result["approval_ids"] == []
    assert exported["run_id"] == result["run_id"]
    assert exported["summary"]["artifacts"] == result["run_artifacts"]
    assert any(
        event["type"] == "tool_observation"
        and event["payload"]["observation"]["tool_name"] == "read_file"
        for event in exported["events"]
    )
