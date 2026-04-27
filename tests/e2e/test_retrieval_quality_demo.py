from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import shutil
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from agent_harness.cli import main


def test_retrieval_quality_demo_golden_path_runs_with_local_qdrant_fixture(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    demo = workspace / "examples" / "retrieval_quality"
    shutil.copytree(repo_root / "examples" / "retrieval_quality", demo)
    monkeypatch.chdir(workspace)
    _install_fake_retrieval_extras(monkeypatch)

    assert (demo / "README.md").exists()
    assert (demo / "config.v2.yaml").exists()
    assert (demo / "policy.v2.yaml").exists()
    assert (demo / "scorecard.yaml").exists()
    assert (demo / "expected" / "retrieval_index.json").exists()
    assert (demo / "expected" / "retrieval_scorecard.json").exists()
    assert {path.name for path in (demo / "docs").rglob("*.md")} >= {
        "architecture.md",
        "coding-rules.md",
        "public-notes.md",
        "semantic-note.md",
        "denied-internal.md",
        "secret-internal.md",
    }

    shutil.copy2(demo / "config.v2.yaml", workspace / "agent-harness.yaml")
    (workspace / "policies").mkdir()
    shutil.copy2(demo / "policies" / "default.json", workspace / "policies" / "default.json")
    shutil.copy2(
        demo / "policies" / "demo-runtime.json",
        workspace / "policies" / "demo-runtime.json",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "demo-retrieval",
                "--paths",
                "examples/retrieval_quality/docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    build = json.loads(capsys.readouterr().out)
    assert build["schema_version"] == "retrieval_index.v1"
    assert build["embedding_backend"] == "fastembed"
    assert build["qdrant_storage_path"] == ".agent-harness/indexes/demo-retrieval/qdrant"
    assert build["remote_embeddings"] is False

    assert (
        main(
            [
                "retrieval",
                "query",
                "demo-retrieval",
                "--query",
                "refactor config loader policy",
                "--mode",
                "hybrid",
                "--k",
                "5",
            ]
        )
        == 0
    )
    query = json.loads(capsys.readouterr().out)
    assert query["retrieval"]["backend"] == "qdrant-local"
    assert query["retrieval"]["remote_embeddings"] is False
    assert any(result["retrieval_method"] == "both" for result in query["results"]), query[
        "results"
    ]

    assert (
        main(
            [
                "retrieval",
                "scorecard",
                "examples/retrieval_quality/scorecard.yaml",
                "--index-id",
                "demo-retrieval",
                "--k",
                "5",
            ]
        )
        == 0
    )
    scorecard = json.loads(capsys.readouterr().out)
    assert scorecard["schema_version"] == "retrieval_scorecard.v1"
    assert scorecard["status"] == "passed"
    assert scorecard["backend_comparison"]
    assert scorecard["metrics"]["hybrid"]["precision_at_k"] > 0
    assert scorecard["metrics"]["hybrid"]["recall_at_k"] == 1.0

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "retrieval-quality-demo")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T16:30:00Z")
    assert main(["run", "examples/retrieval_quality/task.json", "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            workspace
            / ".agent-harness"
            / "runs"
            / "retrieval-quality-demo"
            / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["retrieval"]["backend"] == "qdrant-local"
    assert manifest["retrieval"]["remote_embeddings"] is False
    methods = {item["retrieval_method"] for item in manifest["items"]}
    assert {"lexical", "dense", "both"} <= methods
    rejected_by_path = {item["path"]: item for item in manifest["rejected_items"]}
    assert {
        "examples/retrieval_quality/docs/internal/denied-internal.md",
        "examples/retrieval_quality/docs/internal/secret-internal.md",
    } <= set(rejected_by_path)
    assert rejected_by_path["examples/retrieval_quality/docs/internal/denied-internal.md"][
        "policy_reason"
    ].startswith("path denied by glob")
    assert (
        rejected_by_path["examples/retrieval_quality/docs/internal/secret-internal.md"][
            "policy_reason"
        ]
        == "secret is hard-denied for context"
    )
    assert "do not place in provider input" not in json.dumps(manifest)


def _install_fake_retrieval_extras(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fastembed = types.ModuleType("fastembed")
    fastembed.__spec__ = importlib.machinery.ModuleSpec("fastembed", loader=None)
    fastembed.__version__ = "fake-fastembed-9.9"

    class FakeTextEmbedding:
        def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
            self.model_name = model_name
            self.cache_dir = cache_dir

        def embed(self, documents: list[str]):  # type: ignore[no-untyped-def]
            for document in documents:
                yield _embedding_vector(document)

    fastembed.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]

    qdrant_client = types.ModuleType("qdrant_client")
    qdrant_client.__spec__ = importlib.machinery.ModuleSpec("qdrant_client", loader=None)

    class FakeDistance:
        COSINE = "cosine"

    @dataclass
    class FakeVectorParams:
        size: int
        distance: str

    @dataclass
    class FakePointStruct:
        id: int
        vector: list[float]
        payload: dict[str, object]

    @dataclass
    class FakeScoredPoint:
        payload: dict[str, object]
        score: float

    class FakeQdrantClient:
        stores: dict[str, dict[str, list[FakePointStruct]]] = {}

        def __init__(self, path: str | None = None, url: str | None = None) -> None:
            self.store_key = _store_key(path or url or "memory")
            self.stores.setdefault(self.store_key, {})

        def recreate_collection(
            self,
            *,
            collection_name: str,
            vectors_config: FakeVectorParams,
        ) -> None:
            del vectors_config
            self.stores[self.store_key][collection_name] = []

        def upsert(self, *, collection_name: str, points: list[FakePointStruct]) -> None:
            self.stores[self.store_key][collection_name] = list(points)

        def query_points(
            self,
            *,
            collection_name: str,
            query: list[float],
            limit: int,
            with_payload: bool = True,
        ) -> SimpleNamespace:
            del with_payload
            points = self.stores[self.store_key].get(collection_name, [])
            scored = [FakeScoredPoint(point.payload, _dot(query, point.vector)) for point in points]
            scored = [
                point
                for point in sorted(
                    scored,
                    key=lambda item: (-item.score, str(item.payload["path"])),
                )
                if point.score > 0
            ][:limit]
            return SimpleNamespace(points=scored)

        def close(self) -> None:
            return None

    qdrant_client.QdrantClient = FakeQdrantClient  # type: ignore[attr-defined]
    qdrant_client.models = SimpleNamespace(  # type: ignore[attr-defined]
        Distance=FakeDistance,
        VectorParams=FakeVectorParams,
        PointStruct=FakePointStruct,
    )

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name == "fastembed":
            return fastembed.__spec__
        if name == "qdrant_client":
            return qdrant_client.__spec__
        return real_find_spec(name, package)

    monkeypatch.setitem(sys.modules, "fastembed", fastembed)
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)
    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)


def _embedding_vector(text: str) -> list[float]:
    tokens = {
        token.strip(".,:;()[]").lower()
        for token in text.replace("_", " ").replace("-", " ").split()
    }
    concepts = (
        {"config", "settings"},
        {"loader", "ingestion"},
        {"policy", "governance"},
        {"refactor", "cleanup"},
        {"retrieval"},
        {"architecture"},
        {"evidence"},
    )
    return [1.0 if tokens & concept else 0.0 for concept in concepts]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _store_key(value: str) -> str:
    return str(Path(value).resolve()).casefold() if value != "memory" else value
