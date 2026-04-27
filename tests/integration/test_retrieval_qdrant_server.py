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


@pytest.mark.parametrize(
    "endpoint",
    ["http://localhost:6333", "http://127.0.0.1:6333", "http://[::1]:6333"],
)
def test_qdrant_server_loopback_urls_validate(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
    endpoint: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path, endpoint)

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out

    assert "OK config: agent-harness.yaml artifact_root=.agent-harness" in output


def test_qdrant_server_loopback_build_reports_unreachable_endpoint(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_unreachable_qdrant_server_extras(monkeypatch)
    _seed_project(tmp_path, "http://localhost:6333")
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
                "server-demo",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-server",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert "qdrant-server endpoint is unreachable" in captured.err
    assert "http://localhost:6333" in captured.err
    assert "loopback Qdrant server" in captured.err
    assert not (
        tmp_path / ".agent-harness" / "indexes" / "server-demo" / "retrieval_index.json"
    ).exists()


def test_qdrant_server_loopback_build_and_query_record_endpoint_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_reachable_qdrant_server_extras(monkeypatch)
    _seed_project(tmp_path, "http://127.0.0.1:6333")
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
                "server-demo",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-server",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)

    assert summary["backend"] == "dense"
    assert summary["embedding_backend"] == "fastembed"
    assert summary["embedding_model"] == "BAAI/bge-small-en-v1.5"
    assert summary["embedding_model_version"] == "fake-fastembed-9.9"
    assert summary["qdrant_collection"] == "agent_harness_server_demo"
    assert summary["qdrant_endpoint"] == "http://127.0.0.1:6333"
    assert summary["qdrant_storage_path"] is None
    assert summary["remote_embeddings"] is False

    assert (
        main(
            [
                "retrieval",
                "query",
                "server-demo",
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

    assert result["retrieval"]["requested_backend"] == "dense"
    assert result["retrieval"]["active_backend"] == "qdrant_server_dense"
    assert result["retrieval"]["backend"] == "qdrant-server"
    assert result["retrieval"]["qdrant_collection"] == "agent_harness_server_demo"
    assert result["retrieval"]["qdrant_endpoint"] == "http://127.0.0.1:6333"
    assert result["retrieval"]["remote_embeddings"] is False
    assert result["results"][0]["path"] == "docs/alpha.md"
    assert result["results"][0]["retrieval_method"] == "dense"
    assert result["results"][0]["scores"]["dense"] > 0


def test_qdrant_server_context_assembly_uses_policy_filtered_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _install_reachable_qdrant_server_extras(monkeypatch)
    endpoint = "http://localhost:6333"
    _seed_project(tmp_path, endpoint)
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
                "server-context",
                "--paths",
                "docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "qdrant-server",
            ]
        )
        == 0
    )
    capsys.readouterr()
    _write_config_for_index(tmp_path, "server-context", endpoint)
    restrictive = dict(DEFAULT_POLICY)
    restrictive["name"] = "server-context"
    restrictive["deny_globs"] = [*DEFAULT_POLICY["deny_globs"], "docs/private.md"]
    _write_policy(tmp_path, "server-context", restrictive)
    task_path = _write_task(tmp_path, "server-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-server-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T17:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / "run-server-context" / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["retrieval"]["requested_backend"] == "hybrid"
    assert manifest["retrieval"]["active_backend"] == "qdrant_server_hybrid"
    assert manifest["retrieval"]["backend"] == "qdrant-server"
    assert manifest["retrieval"]["qdrant_endpoint"] == endpoint
    assert manifest["retrieval"]["qdrant_collection"] == "agent_harness_server_context"
    assert manifest["retrieval"]["remote_embeddings"] is False

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


@pytest.mark.retrieval_optional
def test_real_qdrant_server_smoke_is_opt_in(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    if not optional_qdrant_local_dependencies_available():
        pytest.skip("install agent-harness[retrieval] to run qdrant-server smoke")
    if os.environ.get("AGENT_HARNESS_RUN_QDRANT_SERVER_TESTS") != "1":
        pytest.skip("set AGENT_HARNESS_RUN_QDRANT_SERVER_TESTS=1 for loopback server smoke")
    endpoint = os.environ.get("AGENT_HARNESS_QDRANT_SERVER_URL", "http://localhost:6333")
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path, endpoint)
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
                "server-smoke",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "qdrant-server",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)

    assert summary["qdrant_endpoint"] == endpoint
    assert summary["qdrant_collection"] == "agent_harness_server_smoke"


def _install_unreachable_qdrant_server_extras(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fastembed = types.ModuleType("fastembed")
    fastembed.__version__ = "fake-fastembed-9.9"

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
            self.model_name = model_name
            self.cache_dir = cache_dir

        def embed(self, documents: list[str]):  # type: ignore[no-untyped-def]
            for document in documents:
                yield [float(len(document)), 1.0, 0.0]

    fastembed.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]

    qdrant_client = types.ModuleType("qdrant_client")

    class FakeQdrantClient:
        def __init__(self, url: str) -> None:
            raise OSError(f"connection refused: {url}")

    qdrant_client.QdrantClient = FakeQdrantClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", fastembed)
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name in {"fastembed", "qdrant_client"}:
            return importlib.machinery.ModuleSpec(name, loader=None)
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def _install_reachable_qdrant_server_extras(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fastembed = types.ModuleType("fastembed")
    fastembed.__version__ = "fake-fastembed-9.9"

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
            self.model_name = model_name
            self.cache_dir = cache_dir

        def embed(self, documents: list[str]):  # type: ignore[no-untyped-def]
            for document in documents:
                yield [float(len(document)), float(document.count("policy")), 1.0]

    fastembed.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]

    qdrant_client = types.ModuleType("qdrant_client")
    server_state: dict[str, dict[str, object]] = {}

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
        def __init__(self, url: str) -> None:
            self.url = url

        def recreate_collection(
            self,
            collection_name: str,
            vectors_config: FakeVectorParams,
        ) -> bool:
            server_state[collection_name] = {
                "vectors_config": vectors_config,
                "points": [],
            }
            return True

        def upsert(self, collection_name: str, points: list[FakePointStruct]) -> None:
            server_state[collection_name]["points"] = points

        def query_points(
            self,
            collection_name: str,
            query: list[float],
            limit: int,
            with_payload: bool = True,
        ) -> SimpleNamespace:
            del with_payload
            points = [
                SimpleNamespace(
                    payload=point.payload,
                    score=float(point.vector[1]) * float(query[1]),
                )
                for point in server_state[collection_name]["points"]
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


def _seed_project(root: Path, endpoint: str) -> None:
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
                "backend": "qdrant-server",
                "url": endpoint,
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


def _write_config_for_index(root: Path, index_id: str, endpoint: str) -> None:
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
                "backend": "qdrant-server",
                "url": endpoint,
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
                "task_id": "server-context",
                "title": "Assemble qdrant-server retrieval context",
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
