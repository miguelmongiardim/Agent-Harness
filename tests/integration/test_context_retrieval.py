from __future__ import annotations

import json
from pathlib import Path

from agent_harness.context.retrieval import ingest_documents
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.runtimes.native import HarnessRuntime
from agent_harness.schemas import PolicyProfile
from tests.conftest import seed_project


def test_fixed_seed_retrieval_manifest_is_stable_and_logs_denied_retrieval_policy(
    tmp_path: Path, monkeypatch
) -> None:
    seed_project(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "allowed.md").write_text(
        "# Guide\n\nadd_numbers refactor guidance\n", encoding="utf-8"
    )
    (docs_dir / "private.md").write_text(
        "# Private\n\nadd_numbers secret migration notes\n", encoding="utf-8"
    )
    restrictive = dict(DEFAULT_POLICY)
    restrictive["name"] = "retrieval-restrictive"
    restrictive["deny_globs"] = [*DEFAULT_POLICY["deny_globs"], "docs/private.md"]
    (tmp_path / "policies" / "retrieval-restrictive.json").write_text(
        json.dumps(restrictive, indent=2), encoding="utf-8"
    )
    ingest_documents(
        tmp_path,
        tmp_path / ".agent-harness",
        ["docs"],
        PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY)),
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "retrieval-manifest",
                "title": "Retrieve docs into context",
                "intent": "Inspect retrieval context without changing files.",
                "policy_profile": "retrieval-restrictive",
                "context_queries": ["add_numbers"],
                "allowed_tools": [],
                "max_steps": 2,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:00:00Z")

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "retrieval-run-a")
    summary_a = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    manifest_a = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / summary_a.run_id / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )
    events_a = [
        json.loads(line)
        for line in (
            tmp_path / ".agent-harness" / "runs" / summary_a.run_id / "events.jsonl"
        ).read_text(encoding="utf-8").splitlines()
    ]

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "retrieval-run-b")
    summary_b = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    manifest_b = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / summary_b.run_id / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert _stable_manifest(manifest_a) == _stable_manifest(manifest_b)
    assert [source["path"] for source in manifest_a["sources"]] == ["docs/allowed.md"]
    assert manifest_a["sources"][0]["kind"] == "retrieval"
    assert manifest_a["sources"][0]["content_hash"]
    assert manifest_a["sources"][0]["policy_decision_id"]
    assert manifest_a["chunks"][0]["content_hash"]
    assert manifest_a["chunks"][0]["sensitivity"] == "internal"
    assert manifest_a["dense_retrieval"] is None
    assert manifest_a["retrieval"]["active_backend"] == "lexical"
    assert manifest_a["retrieval"]["requested_backend"] == "lexical"
    assert manifest_a["retrieval"]["remote_embeddings"] is False
    rejected_by_path = {item["path"]: item for item in manifest_a["rejected_items"]}
    assert rejected_by_path["docs/private.md"]["policy_allowed"] is False
    assert rejected_by_path["docs/private.md"]["text"] is None
    assert "secret migration notes" not in json.dumps(manifest_a)

    retrieval_decisions = [
        event["payload"]
        for event in events_a
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "retrieval_source"
    ]
    assert {decision["path"] for decision in retrieval_decisions} == {
        "docs/allowed.md",
        "docs/private.md",
    }
    denied = [
        decision["decision"]
        for decision in retrieval_decisions
        if not decision["decision"]["allowed"]
    ]
    assert len(denied) == 1
    assert denied[0]["reason"].startswith("path denied by glob")


def test_ingest_docs_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    seed_project(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# A\n\nalpha\n", encoding="utf-8")
    nested = docs_dir / "nested"
    nested.mkdir()
    (nested / "b.md").write_text("# B\n\nbeta\n", encoding="utf-8")
    policy = PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY))

    first_index = ingest_documents(tmp_path, tmp_path / ".agent-harness", ["docs"], policy)
    first = first_index.read_text(encoding="utf-8")
    second_index = ingest_documents(tmp_path, tmp_path / ".agent-harness", ["docs"], policy)
    second = second_index.read_text(encoding="utf-8")

    assert first == second


def test_retrieved_manifest_redacts_text_and_carries_sensitivity(
    tmp_path: Path, monkeypatch
) -> None:
    seed_project(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "confidential.md").write_text(
        "# Notes\n\ntoken = visible-secret\n", encoding="utf-8"
    )
    sensitive = dict(DEFAULT_POLICY)
    sensitive["name"] = "retrieval-sensitive"
    sensitive["sensitivity_rules"] = [
        *DEFAULT_POLICY["sensitivity_rules"],
        {"pattern": "docs/confidential.md", "classification": "confidential"},
    ]
    (tmp_path / "policies" / "retrieval-sensitive.json").write_text(
        json.dumps(sensitive, indent=2), encoding="utf-8"
    )
    ingest_documents(
        tmp_path,
        tmp_path / ".agent-harness",
        ["docs"],
        PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY)),
    )
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "retrieval-sensitive",
                "title": "Retrieve sensitive docs into context",
                "intent": "Inspect retrieval context without changing files.",
                "policy_profile": "retrieval-sensitive",
                "context_queries": ["token"],
                "allowed_tools": [],
                "max_steps": 2,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "retrieval-sensitive-run")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-25T14:15:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / summary.run_id / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["sources"][0]["path"] == "docs/confidential.md"
    assert manifest["sources"][0]["sensitivity"] == "confidential"
    assert manifest["chunks"][0]["sensitivity"] == "confidential"
    assert "[REDACTED]" in manifest["chunks"][0]["text"]
    assert "visible-secret" not in manifest["chunks"][0]["text"]


def _stable_manifest(manifest: dict[str, object]) -> dict[str, object]:
    stable = dict(manifest)
    stable.pop("manifest_id", None)
    stable.pop("run_id", None)
    stable.pop("created_at", None)
    return stable
