from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_swebench_style_adapter_import_run_export_points_to_real_run_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["benchmark", "run", "local-samples", "swebench-python-refactor"]) == 0
    result = json.loads(capsys.readouterr().out)

    evidence = result["adapter_evidence"]
    assert result["adapter_id"] == "swebench_style"
    assert evidence["adapter_id"] == "swebench_style"
    assert evidence["task_import"]["task_id"] == "benchmark-swebench-python-refactor"
    assert evidence["task_import"]["task_path"] == result["task_path"]
    assert evidence["workspace_preparation"]["workspace"] == result["workspace"]
    assert evidence["workspace_preparation"]["workspace_files"] == ["fixtures/legacy_math.py"]
    assert evidence["policy_selection"] == {
        "profile": "default",
        "policy_path": "policies/default.json",
    }
    assert evidence["run_execution"]["run_id"] == result["run_id"]
    assert evidence["run_execution"]["status"] == "completed"
    assert evidence["eval_result_mapping"] == {
        "expected_status": "completed",
        "actual_status": "completed",
        "passed": True,
    }
    assert evidence["export"]["result_artifact"] == result["result_artifact"]
    assert evidence["export"]["run_export"] == result["run_export"]

    exported = json.loads((tmp_path / result["run_export"]).read_text(encoding="utf-8"))
    assert exported["run_id"] == result["run_id"]
    assert exported["summary"]["artifacts"] == result["run_artifacts"]
    assert any(event["type"] == "approval_decided" for event in exported["events"])


def test_terminal_bench_style_adapter_import_run_export_points_to_real_run_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["benchmark", "run", "local-samples", "terminal-readonly-inspect"]) == 0
    result = json.loads(capsys.readouterr().out)

    evidence = result["adapter_evidence"]
    assert result["adapter_id"] == "terminal_bench_style"
    assert evidence["adapter_id"] == "terminal_bench_style"
    assert evidence["task_import"]["task_id"] == "benchmark-terminal-readonly-inspect"
    assert evidence["workspace_preparation"]["workspace_files"] == ["workspace/README.md"]
    assert evidence["policy_selection"] == {
        "profile": "default",
        "policy_path": "policies/default.json",
    }
    assert evidence["run_execution"]["status"] == "completed"
    assert evidence["eval_result_mapping"]["passed"] is True
    assert result["approval_ids"] == []

    exported = json.loads((tmp_path / result["run_export"]).read_text(encoding="utf-8"))
    assert exported["run_id"] == result["run_id"]
    assert exported["summary"]["artifacts"] == result["run_artifacts"]
    assert any(
        event["type"] == "tool_observation"
        and event["payload"]["observation"]["tool_name"] == "read_file"
        for event in exported["events"]
    )


def test_benchmark_adapter_exercises_local_dense_retrieval_fixture(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    monkeypatch.setattr(
        "agent_harness.core.runtime.optional_dense_dependencies_available",
        lambda: True,
    )

    assert main(["benchmark", "run", "local-samples", "swebench-dense-retrieval"]) == 0
    result = json.loads(capsys.readouterr().out)

    manifest_path = tmp_path / result["workspace"] / result["run_artifacts"]["context_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["adapter_id"] == "swebench_style"
    assert result["adapter_evidence"]["retrieval"] == {
        "requested_backend": "qdrant",
        "active_backend": "local_dense_fixture",
        "remote_embeddings": False,
    }
    assert manifest["retrieval"]["requested_backend"] == "qdrant"
    assert manifest["retrieval"]["active_backend"] == "local_dense_fixture"
    assert manifest["retrieval"]["remote_embeddings"] is False
    assert manifest["dense_retrieval"]["backend"] == "local_token_similarity"
    assert any(item["retrieval_method"] in {"dense", "both"} for item in manifest["items"])
