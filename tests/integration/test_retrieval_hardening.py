from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.context.retrieval import ingest_documents
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.runtimes.native import HarnessRuntime
from agent_harness.schemas import PolicyProfile


def test_missing_dense_dependencies_warn_and_fall_back_to_lexical_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path, retrieval_backend="qdrant")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "# Guide\n\nadd_numbers refactor guidance\n",
        encoding="utf-8",
    )
    ingest_documents(
        tmp_path,
        tmp_path / ".agent-harness",
        ["docs"],
        PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY)),
    )
    task_path = _write_task(tmp_path, "missing-dense-dependencies")
    _hide_optional_retrieval_dependencies(monkeypatch)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-missing-dense-deps")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:35:00Z")

    assert main(["doctor"]) == 0
    doctor = capsys.readouterr().out
    assert "WARN optional retrieval: qdrant-client/fastembed unavailable" in doctor

    summary = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    manifest = json.loads(
        (tmp_path / ".agent-harness" / "runs" / summary.run_id / "context_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary.status == "dry_run"
    assert manifest["retrieval"]["active_backend"] == "lexical"
    assert manifest["retrieval"]["requested_backend"] == "qdrant"
    assert manifest["retrieval"]["fallback_reason"] == "missing_optional_dependencies"
    assert manifest["retrieval"]["remote_embeddings"] is False
    assert manifest["dense_retrieval"] is None
    assert [item["retrieval_method"] for item in manifest["items"]] == ["lexical"]
    assert manifest["items"][0]["scores"] == {"lexical": 1.0}


def _seed_project(root: Path, retrieval_backend: str) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": retrieval_backend,
        "template_catalog": "bundled",
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def _write_task(root: Path, task_id: str) -> Path:
    path = root / "task.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": task_id,
                "title": "Retrieve docs",
                "intent": "Inspect retrieval context without changing files.",
                "context_queries": ["add_numbers"],
                "allowed_tools": [],
                "max_steps": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _hide_optional_retrieval_dependencies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name in {"qdrant_client", "fastembed"}:
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
