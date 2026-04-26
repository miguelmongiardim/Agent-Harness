from __future__ import annotations

import json
from pathlib import Path

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.retrieval import RetrievedChunk, ingest_documents
from agent_harness.runtime import HarnessRuntime
from agent_harness.schemas import PolicyProfile
from tests.conftest import seed_project


class _DenseFixtureRetriever:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        del queries
        return [
            RetrievedChunk(
                source_id="dense-both",
                path="docs/both.md",
                text="# Both\n\nadd_numbers shared guidance\n",
                score=0.92,
                start_line=1,
                end_line=3,
            ),
            RetrievedChunk(
                source_id="dense-only",
                path="docs/dense.md",
                text="# Dense\n\nsemantic helper guidance\n",
                score=0.73,
                start_line=1,
                end_line=3,
            ),
        ][:limit]

    def metadata(self) -> dict[str, str]:
        return {
            "backend": "local_fixture",
            "model": "fixture-embeddings",
            "version": "baseline",
        }


def _seed_project_with_mock_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "mock-default",
        "provider_profiles": [
            {
                "provider_profile_id": "mock-default",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic",
                "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
                "network": False,
                "requires_approval": False,
            }
        ],
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def test_hybrid_retrieval_manifest_deduplicates_overlap_and_records_rejected_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed_project(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "both.md").write_text(
        "# Both\n\nadd_numbers shared guidance\n", encoding="utf-8"
    )
    (docs_dir / "lexical.md").write_text(
        "# Lexical\n\nadd_numbers exact symbol notes\n", encoding="utf-8"
    )
    (docs_dir / "dense.md").write_text(
        "# Dense\n\nsemantic helper guidance\n", encoding="utf-8"
    )
    (docs_dir / "private.md").write_text(
        "# Private\n\nadd_numbers private denied notes\n", encoding="utf-8"
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
                "task_id": "hybrid-retrieval",
                "title": "Assemble hybrid retrieval context",
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
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-hybrid-retrieval")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T18:00:00Z")
    monkeypatch.setattr(
        "agent_harness.runtime.LocalDenseRetriever",
        _DenseFixtureRetriever,
        raising=False,
    )

    summary = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / summary.run_id / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == "context_manifest.v2"
    assert manifest["dense_retrieval"] == {
        "backend": "local_fixture",
        "model": "fixture-embeddings",
        "version": "baseline",
    }

    included_by_path = {item["path"]: item for item in manifest["items"]}
    assert set(included_by_path) == {"docs/both.md", "docs/lexical.md", "docs/dense.md"}
    assert included_by_path["docs/both.md"]["retrieval_method"] == "both"
    assert included_by_path["docs/lexical.md"]["retrieval_method"] == "lexical"
    assert included_by_path["docs/dense.md"]["retrieval_method"] == "dense"
    assert {entry["method"] for entry in included_by_path["docs/both.md"]["provenance"]} == {
        "lexical",
        "dense",
    }
    assert included_by_path["docs/both.md"]["scores"] == {"lexical": 1.0, "dense": 0.92}
    assert len([item for item in manifest["items"] if item["path"] == "docs/both.md"]) == 1

    rejected_by_path = {item["path"]: item for item in manifest["rejected_items"]}
    assert list(rejected_by_path) == ["docs/private.md"]
    assert rejected_by_path["docs/private.md"]["retrieval_method"] == "lexical"
    assert rejected_by_path["docs/private.md"]["policy_allowed"] is False
    assert rejected_by_path["docs/private.md"]["policy_reason"].startswith(
        "path denied by glob"
    )
    assert rejected_by_path["docs/private.md"]["text"] is None
    assert "private denied notes" not in json.dumps(rejected_by_path["docs/private.md"])


def test_provider_input_records_reference_manifest_items_for_retrieved_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_project_with_mock_provider(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "public.md").write_text(
        "# Public\n\nadd_numbers provider context\n", encoding="utf-8"
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
                "schema_version": "task.v2",
                "task_id": "provider-input-manifest",
                "title": "Bind provider input to manifest items",
                "intent": "Inspect retrieval context without changing files.",
                "context_queries": ["add_numbers"],
                "allowed_tools": [],
                "max_steps": 2,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-provider-input-manifest")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T18:30:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path, dry_run=True)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary.run_id
    manifest = json.loads((run_dir / "context_manifest.json").read_text(encoding="utf-8"))
    provider_input = json.loads((run_dir / "provider_input.json").read_text(encoding="utf-8"))

    manifest_item = manifest["items"][0]
    record = provider_input["records"][0]

    assert record["path"] == manifest_item["path"]
    assert record["manifest_item_id"] == manifest_item["item_id"]
    assert record["chunk_id"] == manifest_item["chunk_id"]
    assert record["content_hash"] == manifest_item["content_hash"]
    assert record["text"] == manifest_item["text"]
