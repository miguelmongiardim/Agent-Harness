from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_harness.cli import main
from agent_harness.context.qdrant_local import optional_qdrant_local_dependencies_available
from agent_harness.defaults import DEFAULT_POLICY

pytestmark = pytest.mark.slow


def test_qdrant_local_index_build_records_fastembed_and_storage_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fake_retrieval_extras(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-demo",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    manifest = json.loads((tmp_path / summary["manifest_path"]).read_text(encoding="utf-8"))

    assert summary["schema_version"] == "retrieval_index.v1"
    assert summary["backend"] == "dense"
    assert summary["embedding_backend"] == "fastembed"
    assert summary["embedding_model"] == "BAAI/bge-small-en-v1.5"
    assert summary["embedding_model_version"] == "fake-fastembed-9.9"
    assert summary["qdrant_collection"] == "agent_harness_qdrant_demo"
    assert summary["qdrant_storage_path"] == ".agent-harness/indexes/qdrant-demo/qdrant"
    assert summary["remote_embeddings"] is False
    assert manifest["qdrant_collection"] == summary["qdrant_collection"]
    assert manifest["qdrant_storage_path"] == summary["qdrant_storage_path"]
    assert (tmp_path / summary["index_path"]).exists()
    assert (tmp_path / summary["qdrant_storage_path"] / "points.json").exists()


def test_qdrant_local_dense_query_records_backend_evidence_and_results(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fake_retrieval_extras(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "# Alpha\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    (docs / "beta.md").write_text("# Beta\n\nunrelated release notes\n", encoding="utf-8")
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-demo",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "retrieval",
                "query",
                "qdrant-demo",
                "--query",
                "config loader policy",
                "--mode",
                "dense",
                "--k",
                "2",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "retrieval_query.v1"
    assert result["index_id"] == "qdrant-demo"
    assert result["mode"] == "dense"
    assert result["retrieval"]["schema_version"] == "retrieval_backend.v2"
    assert result["retrieval"]["requested_backend"] == "dense"
    assert result["retrieval"]["active_backend"] == "qdrant_local_dense"
    assert result["retrieval"]["backend"] == "qdrant-local"
    assert result["retrieval"]["embedding_model"] == "BAAI/bge-small-en-v1.5"
    assert result["retrieval"]["embedding_model_version"] == "fake-fastembed-9.9"
    assert result["retrieval"]["qdrant_collection"] == "agent_harness_qdrant_demo"
    assert result["retrieval"]["qdrant_storage_path"] == (
        ".agent-harness/indexes/qdrant-demo/qdrant"
    )
    assert result["retrieval"]["remote_embeddings"] is False
    assert result["results"][0]["path"] == "docs/alpha.md"
    assert result["results"][0]["retrieval_method"] == "dense"
    assert set(result["results"][0]["scores"]) == {"dense"}
    assert result["results"][0]["scores"]["dense"] > 0
    assert result["results"][0]["provenance"] == [
        {"method": "dense", "score": result["results"][0]["scores"]["dense"]}
    ]


def test_qdrant_local_hybrid_context_assembly_uses_policy_filtered_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fake_retrieval_extras(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "both.md").write_text(
        "# Both\n\nconfig loader policy shared guidance\n",
        encoding="utf-8",
    )
    (docs / "private.md").write_text(
        "# Private\n\nconfig loader policy private denied notes\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-context",
                "--paths",
                "docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _write_config_for_index(tmp_path, "qdrant-context")
    restrictive = dict(DEFAULT_POLICY)
    restrictive["name"] = "qdrant-context"
    restrictive["deny_globs"] = [*DEFAULT_POLICY["deny_globs"], "docs/private.md"]
    _write_policy(tmp_path, "qdrant-context", restrictive)
    task_path = _write_task(tmp_path, "qdrant-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-qdrant-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T16:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / "run-qdrant-context" / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["retrieval"]["requested_backend"] == "hybrid"
    assert manifest["retrieval"]["active_backend"] == "qdrant_local_hybrid"
    assert manifest["retrieval"]["backend"] == "qdrant-local"
    assert manifest["retrieval"]["embedding_model"] == "BAAI/bge-small-en-v1.5"
    assert manifest["retrieval"]["embedding_model_version"] == "fake-fastembed-9.9"
    assert manifest["retrieval"]["qdrant_collection"] == "agent_harness_qdrant_context"
    assert manifest["retrieval"]["remote_embeddings"] is False
    assert manifest["dense_retrieval"] == {
        "backend": "qdrant-local",
        "model": "BAAI/bge-small-en-v1.5",
        "version": "fake-fastembed-9.9",
    }

    included_by_path = {item["path"]: item for item in manifest["items"]}
    assert set(included_by_path) == {"docs/both.md"}
    assert included_by_path["docs/both.md"]["retrieval_method"] == "both"
    assert set(included_by_path["docs/both.md"]["scores"]) == {"lexical", "dense"}

    rejected_by_path = {item["path"]: item for item in manifest["rejected_items"]}
    assert set(rejected_by_path) == {"docs/private.md"}
    assert rejected_by_path["docs/private.md"]["policy_allowed"] is False
    assert rejected_by_path["docs/private.md"]["retrieval_method"] == "both"
    assert rejected_by_path["docs/private.md"]["text"] is None
    assert "private denied notes" not in json.dumps(manifest)


def test_qdrant_local_build_reports_missing_optional_dependencies(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _hide_optional_retrieval_dependencies(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-missing",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "qdrant-local retrieval requires agent-harness[retrieval]" in captured.err
    assert "fastembed" in captured.err
    assert "qdrant-client" in captured.err
    assert not (
        tmp_path / ".agent-harness" / "indexes" / "qdrant-missing" / "retrieval_index.json"
    ).exists()
    _install_fake_retrieval_extras(monkeypatch)
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-missing",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )


def test_qdrant_local_overwrite_and_delete_manage_persistent_storage(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_fake_retrieval_extras(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    source.write_text("# Guide\n\nfirst policy retrieval\n", encoding="utf-8")
    build_args = [
        "retrieval",
        "index",
        "build",
        "--index-id",
        "qdrant-demo",
        "--paths",
        "docs",
        "--mode",
        "dense",
        "--dense-backend",
        "qdrant-local",
    ]
    assert main(build_args) == 0
    first = json.loads(capsys.readouterr().out)
    first_storage = tmp_path / first["qdrant_storage_path"]
    assert (first_storage / "points.json").exists()
    source.write_text("# Guide\n\nupdated policy retrieval\n", encoding="utf-8")

    assert main([*build_args, "--overwrite"]) == 0
    second = json.loads(capsys.readouterr().out)
    points = json.loads((tmp_path / second["qdrant_storage_path"] / "points.json").read_text())

    assert second["qdrant_storage_path"] == first["qdrant_storage_path"]
    assert second["source_hashes"]["docs/guide.md"] != first["source_hashes"]["docs/guide.md"]
    assert "updated policy retrieval" in points["points"][0]["payload"]["text"]
    assert "first policy retrieval" not in json.dumps(points)

    assert main(["retrieval", "index", "delete", "qdrant-demo"]) == 0
    deleted = json.loads(capsys.readouterr().out)
    assert deleted == {"deleted": "qdrant-demo"}
    assert not (tmp_path / ".agent-harness" / "indexes" / "qdrant-demo").exists()


@pytest.mark.retrieval_optional
def test_real_qdrant_local_retrieval_extra_smoke_is_opt_in(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    if not optional_qdrant_local_dependencies_available():
        pytest.skip("install agent-harness[retrieval] to run qdrant-local smoke")
    if os.environ.get("AGENT_HARNESS_RUN_RETRIEVAL_OPTIONAL_TESTS") != "1":
        pytest.skip("set AGENT_HARNESS_RUN_RETRIEVAL_OPTIONAL_TESTS=1 for local model smoke")
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-smoke",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)

    assert summary["embedding_backend"] == "fastembed"
    assert summary["qdrant_collection"] == "agent_harness_qdrant_smoke"
    assert summary["qdrant_storage_path"] == ".agent-harness/indexes/qdrant-smoke/qdrant"


def _install_fake_retrieval_extras(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fastembed = types.ModuleType("fastembed")
    fastembed.__version__ = "fake-fastembed-9.9"

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
            self.model_name = model_name
            self.cache_dir = cache_dir

        def embed(self, documents: list[str]):  # type: ignore[no-untyped-def]
            for document in documents:
                length = float(len(document))
                yield [length, float(document.count("policy")), 1.0]

    fastembed.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]

    qdrant_client = types.ModuleType("qdrant_client")

    class FakeDistance:
        COSINE = "Cosine"

    class FakeVectorParams:
        def __init__(self, size: int, distance: str) -> None:
            self.size = size
            self.distance = distance

    class FakePointStruct:
        def __init__(
            self,
            id: int,  # noqa: A002
            vector: list[float],
            payload: dict[str, object],
        ) -> None:
            self.id = id
            self.vector = vector
            self.payload = payload

    class FakeQdrantClient:
        def __init__(self, path: str) -> None:
            self.path = Path(path)
            self.path.mkdir(parents=True, exist_ok=True)

        def recreate_collection(
            self,
            collection_name: str,
            vectors_config: FakeVectorParams,
        ) -> bool:
            (self.path / "collection.json").write_text(
                json.dumps(
                    {
                        "collection_name": collection_name,
                        "vector_size": vectors_config.size,
                        "distance": vectors_config.distance,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return True

        def upsert(self, collection_name: str, points: list[FakePointStruct]) -> None:
            (self.path / "points.json").write_text(
                json.dumps(
                    {
                        "collection_name": collection_name,
                        "points": [
                            {
                                "id": point.id,
                                "vector": point.vector,
                                "payload": point.payload,
                            }
                            for point in points
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        def query_points(self, collection_name: str, query: list[float], limit: int):
            payload = json.loads((self.path / "points.json").read_text(encoding="utf-8"))
            points = [
                SimpleNamespace(
                    payload=point["payload"],
                    score=float(point["vector"][1]) * float(query[1]),
                )
                for point in payload["points"]
                if payload["collection_name"] == collection_name
            ]
            points.sort(key=lambda point: -point.score)
            return SimpleNamespace(points=points[:limit])

        def close(self) -> None:
            return None

    qdrant_client.QdrantClient = FakeQdrantClient  # type: ignore[attr-defined]
    qdrant_client.models = SimpleNamespace(
        Distance=FakeDistance,
        PointStruct=FakePointStruct,
        VectorParams=FakeVectorParams,
    )
    monkeypatch.setitem(sys.modules, "fastembed", fastembed)
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name in {"fastembed", "qdrant_client"}:
            return importlib.machinery.ModuleSpec(name, loader=None)
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def _hide_optional_retrieval_dependencies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name in {"qdrant_client", "fastembed"}:
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def _seed_project(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "retrieval": {
            "default_mode": "dense",
            "dense": {
                "embedding_backend": "fastembed",
                "embedding_provider": "fastembed",
                "remote_embeddings": False,
            },
            "qdrant": {
                "backend": "qdrant-local",
            },
        },
        "template_catalog": "bundled",
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def _write_config_for_index(root: Path, index_id: str) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "retrieval": {
            "index_id": index_id,
            "default_mode": "hybrid",
            "dense": {
                "embedding_backend": "fastembed",
                "embedding_provider": "fastembed",
                "remote_embeddings": False,
            },
            "qdrant": {
                "backend": "qdrant-local",
            },
        },
        "template_catalog": "bundled",
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _write_policy(root: Path, name: str, policy: dict[str, object]) -> None:
    policies = root / "policies"
    policies.mkdir(exist_ok=True)
    (policies / f"{name}.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")


def _write_task(root: Path, policy_profile: str) -> Path:
    path = root / "task.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "qdrant-context",
                "title": "Assemble qdrant-local retrieval context",
                "intent": "Inspect retrieval context without changing files.",
                "policy_profile": policy_profile,
                "context_queries": ["config loader policy"],
                "allowed_tools": [],
                "max_steps": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
