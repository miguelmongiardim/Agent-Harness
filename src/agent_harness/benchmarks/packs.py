from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import Any, cast

from agent_harness.benchmarks.adapters import BenchmarkAdapterContext, adapter_for_case
from agent_harness.benchmarks.schema import (
    BenchmarkCaseRecord,
    BenchmarkPackRecord,
    BenchmarkResult,
)
from agent_harness.config import dump_model, write_default_config
from agent_harness.context.retrieval import ingest_documents
from agent_harness.core.runtime import HarnessRuntime, approve_action
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.exporters import export_json
from agent_harness.policy import PolicyEngine
from agent_harness.policy.schema import PolicyProfile
from agent_harness.storage import RunStore
from agent_harness.storage.schema import ApprovalRecord, RunSummary
from agent_harness.utils import load_json, write_json

BUNDLED_PACKS = {"local-samples": "local-samples.json"}


def list_benchmark_packs() -> list[BenchmarkPackRecord]:
    return [load_benchmark_pack(pack_id) for pack_id in sorted(BUNDLED_PACKS)]


def load_benchmark_pack(pack_id: str) -> BenchmarkPackRecord:
    filename = BUNDLED_PACKS.get(pack_id)
    if filename is None:
        raise ValueError(f"benchmark pack not found: {pack_id}")
    text = (
        resources.files("agent_harness.bundled_benchmarks")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return BenchmarkPackRecord.model_validate_json(text)


def run_benchmark_case(project_root: Path, pack_id: str, case_id: str) -> BenchmarkResult:
    project_root = project_root.resolve()
    pack = load_benchmark_pack(pack_id)
    case = _case_by_id(pack, case_id)
    workspace = _prepare_benchmark_workspace(project_root, pack, case)
    task_path = workspace / "task.json"
    dump_model(task_path, case.task)

    summary = HarnessRuntime(workspace).run_task(task_path, dry_run=False)
    approval_ids = list(summary.approvals)
    if summary.status == "paused" and case.auto_approve_patches:
        approval_ids = _approve_pending_patch_actions(workspace, summary)
        summary = _read_summary(workspace, summary.run_id)

    store = RunStore.open_existing(workspace / ".agent-harness", summary.run_id)
    result_dir = project_root / ".agent-harness" / "benchmarks" / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    export_path = result_dir / f"{pack.pack_id}-{case.case_id}-{summary.run_id}-run.json"
    export_json(store, export_path)

    result_path = result_dir / f"{pack.pack_id}-{case.case_id}-{summary.run_id}.json"
    workspace_relative = _project_relative(project_root, workspace)
    task_relative = _project_relative(project_root, task_path)
    result_relative = _project_relative(project_root, result_path)
    export_relative = _project_relative(project_root, export_path)
    adapter = adapter_for_case(case)
    passed = summary.status == case.expected_status
    adapter_evidence = adapter.evidence(
        BenchmarkAdapterContext(
            case=case,
            workspace=workspace_relative,
            task_path=task_relative,
            run_id=summary.run_id,
            status=summary.status,
            passed=passed,
            result_artifact=result_relative,
            run_export=export_relative,
            retrieval=_retrieval_evidence(workspace, summary),
        )
    )
    result = BenchmarkResult(
        pack_id=pack.pack_id,
        version=pack.version,
        case_id=case.case_id,
        benchmark_kind=case.benchmark_kind,
        adapter_id=adapter.adapter_id,
        run_id=summary.run_id,
        task_id=summary.task_id,
        status=summary.status,
        passed=passed,
        workspace=workspace_relative,
        task_path=task_relative,
        result_artifact=result_relative,
        run_export=export_relative,
        run_artifacts=summary.artifacts,
        adapter_evidence=adapter_evidence,
        approval_ids=approval_ids,
    )
    write_json(result_path, result.model_dump(mode="json"))
    return result


def _case_by_id(pack: BenchmarkPackRecord, case_id: str) -> BenchmarkCaseRecord:
    for case in pack.cases:
        if case.case_id == case_id:
            return case
    raise ValueError(f"benchmark case not found: {pack.pack_id}/{case_id}")


def _prepare_benchmark_workspace(
    project_root: Path,
    pack: BenchmarkPackRecord,
    case: BenchmarkCaseRecord,
) -> Path:
    workspace = (
        project_root / ".agent-harness" / "benchmarks" / "workspaces" / pack.pack_id / case.case_id
    )
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    _write_benchmark_config(workspace, pack, case)
    write_json(workspace / "policies" / "default.json", DEFAULT_POLICY)
    for file in case.workspace_files:
        path = workspace / file.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content, encoding="utf-8")
    if case.ingest_paths:
        ingest_documents(
            workspace,
            workspace / ".agent-harness",
            case.ingest_paths,
            PolicyEngine(workspace, PolicyProfile.model_validate(DEFAULT_POLICY)),
        )
    return workspace


def _write_benchmark_config(
    workspace: Path, pack: BenchmarkPackRecord, case: BenchmarkCaseRecord
) -> None:
    write_default_config(workspace, force=True)
    write_json(
        workspace / "agent-harness.yaml",
        {
            "schema_version": "config.v2",
            "project_name": f"{pack.pack_id}-{case.case_id}",
            "artifact_root": ".agent-harness",
            "default_policy": "default",
            "retrieval_backend": case.retrieval_backend,
            "template_catalog": "bundled",
        },
    )


def _approve_pending_patch_actions(workspace: Path, summary: RunSummary) -> list[str]:
    store = RunStore.open_existing(workspace / ".agent-harness", summary.run_id)
    approved: list[str] = []
    for action_id in summary.approvals:
        approval = store.read_approval(action_id)
        if approval.tool_name != "patch_file" or approval.status != "pending":
            continue
        approved_record: ApprovalRecord = approve_action(
            workspace,
            summary.run_id,
            action_id,
            decision="approve",
            actor="benchmark",
            reason="sample benchmark auto-review",
        )
        approved.append(approved_record.action_id)
    return approved


def _read_summary(workspace: Path, run_id: str) -> RunSummary:
    return RunSummary.model_validate_json(
        (workspace / ".agent-harness" / "runs" / run_id / "summary.json").read_text(
            encoding="utf-8"
        )
    )


def _retrieval_evidence(workspace: Path, summary: RunSummary) -> dict[str, str | bool]:
    manifest_relative = summary.artifacts.get("context_manifest")
    if manifest_relative is None:
        return {}
    manifest = cast(dict[str, Any], load_json(workspace / manifest_relative))
    retrieval = manifest.get("retrieval")
    if not isinstance(retrieval, dict):
        return {}
    return {
        "requested_backend": str(retrieval.get("requested_backend", "")),
        "active_backend": str(retrieval.get("active_backend", "")),
        "remote_embeddings": retrieval.get("remote_embeddings") is True,
    }


def _project_relative(project_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        return str(resolved)
