from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from agent_harness.context.chunking import RetrievedChunk, chunk_text
from agent_harness.context.qdrant_local import (
    FASTEMBED_DEFAULT_MODEL,
    optional_qdrant_local_dependencies_available,
    query_qdrant_local_collection,
    query_qdrant_server_collection,
)
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import DenseRetrievalMetadata
from agent_harness.utils import sha256_text, stable_id


class Retriever(Protocol):
    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]: ...


class DenseRetriever(Retriever, Protocol):
    def metadata(self) -> DenseRetrievalMetadata: ...


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self.chunks = chunks or []

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        del queries
        return self.chunks[:limit]


class LexicalRetriever:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        if not self.index_path.exists():
            return []
        terms = {term.lower() for query in queries for term in query.split() if term}
        scored: list[RetrievedChunk] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            text = str(record["text"])
            haystack = text.lower()
            score = sum(1.0 for term in terms if term in haystack)
            if score > 0 or not terms:
                scored.append(
                    RetrievedChunk(
                        source_id=str(record["source_id"]),
                        path=str(record["path"]),
                        text=text,
                        score=score,
                        start_line=int(record.get("start_line", 1)),
                        end_line=int(record.get("end_line", 1)),
                    )
                )
        return sorted(scored, key=lambda chunk: (-chunk.score, chunk.path, chunk.start_line))[
            :limit
        ]


class QdrantFastEmbedRetriever:
    def __init__(self) -> None:
        try:
            import fastembed  # type: ignore[import-not-found]  # noqa: F401
            import qdrant_client  # type: ignore[import-not-found]  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "qdrant-client and fastembed are optional retrieval dependencies"
            ) from exc

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        del queries, limit
        raise RuntimeError("Qdrant/FastEmbed retrieval is smoke-only in the current repo")


class QdrantLocalRetriever:
    def __init__(
        self,
        storage_path: Path,
        collection_name: str,
        *,
        model: str = FASTEMBED_DEFAULT_MODEL,
        version: str = "unknown",
        cache_dir: Path | None = None,
    ) -> None:
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.model = model
        self.version = version
        self.cache_dir = cache_dir

    def metadata(self) -> DenseRetrievalMetadata:
        return DenseRetrievalMetadata(
            backend="qdrant-local",
            model=self.model,
            version=self.version,
        )

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        query = " ".join(queries)
        if not query:
            return []
        results = query_qdrant_local_collection(
            storage_path=self.storage_path,
            collection_name=self.collection_name,
            query=query,
            model_name=self.model,
            cache_dir=self.cache_dir,
            limit=limit,
        )
        chunks: list[RetrievedChunk] = []
        for result in results:
            if not result["path"]:
                continue
            chunks.append(
                RetrievedChunk(
                    source_id=str(result["source_id"]),
                    path=str(result["path"]),
                    text=str(result["text"]),
                    score=_result_float(result, "score"),
                    start_line=_result_int(result, "start_line"),
                    end_line=_result_int(result, "end_line"),
                )
            )
        return chunks


class QdrantServerRetriever:
    def __init__(
        self,
        endpoint: str,
        collection_name: str,
        *,
        model: str = FASTEMBED_DEFAULT_MODEL,
        version: str = "unknown",
        cache_dir: Path | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.collection_name = collection_name
        self.model = model
        self.version = version
        self.cache_dir = cache_dir

    def metadata(self) -> DenseRetrievalMetadata:
        return DenseRetrievalMetadata(
            backend="qdrant-server",
            model=self.model,
            version=self.version,
        )

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        query = " ".join(queries)
        if not query:
            return []
        results = query_qdrant_server_collection(
            endpoint=self.endpoint,
            collection_name=self.collection_name,
            query=query,
            model_name=self.model,
            cache_dir=self.cache_dir,
            limit=limit,
        )
        chunks: list[RetrievedChunk] = []
        for result in results:
            if not result["path"]:
                continue
            chunks.append(
                RetrievedChunk(
                    source_id=str(result["source_id"]),
                    path=str(result["path"]),
                    text=str(result["text"]),
                    score=_result_float(result, "score"),
                    start_line=_result_int(result, "start_line"),
                    end_line=_result_int(result, "end_line"),
                )
            )
        return chunks


def _result_float(result: dict[str, object], key: str) -> float:
    value = result[key]
    if not isinstance(value, int | float | str):
        raise ValueError(f"retrieval result field must be numeric: {key}")
    return float(value)


def _result_int(result: dict[str, object], key: str) -> int:
    value = result[key]
    if not isinstance(value, int | float | str):
        raise ValueError(f"retrieval result field must be int: {key}")
    return int(value)


class LocalDenseRetriever:
    def __init__(
        self,
        index_path: Path,
        *,
        backend: str = "local_token_similarity",
        model: str = "token-set",
        version: str = "baseline",
    ) -> None:
        self.index_path = index_path
        self.backend = backend
        self.model = model
        self.version = version

    def metadata(self) -> DenseRetrievalMetadata:
        return DenseRetrievalMetadata(
            backend=self.backend,
            model=self.model,
            version=self.version,
        )

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        if not self.index_path.exists():
            return []
        query_tokens = _dense_tokens(" ".join(queries))
        if not query_tokens:
            return []
        scored: list[RetrievedChunk] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            text = str(record["text"])
            tokens = _dense_tokens(text)
            score = _jaccard_score(query_tokens, tokens)
            if score <= 0.0:
                continue
            scored.append(
                RetrievedChunk(
                    source_id=str(record["source_id"]),
                    path=str(record["path"]),
                    text=text,
                    score=score,
                    start_line=int(record.get("start_line", 1)),
                    end_line=int(record.get("end_line", 1)),
                )
            )
        return sorted(scored, key=lambda chunk: (-chunk.score, chunk.path, chunk.start_line))[
            :limit
        ]


def ingest_documents(
    project_root: Path, artifact_root: Path, paths: list[str], policy: PolicyEngine
) -> Path:
    index_path = artifact_root / "indexes" / "documents.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for raw_path in paths:
        root = (project_root / raw_path).resolve()
        candidates = (
            [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        )
        for candidate in candidates:
            rel = candidate.relative_to(project_root).as_posix()
            decision = policy.evaluate_context_source(rel)
            if not decision.allowed:
                continue
            text = candidate.read_text(encoding="utf-8")
            source_id = stable_id("source", rel, sha256_text(text))
            for chunk in chunk_text(text, source_id, rel):
                records.append(
                    {
                        "source_id": source_id,
                        "path": rel,
                        "text": chunk.text,
                        "text_hash": sha256_text(chunk.text),
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                    }
                )
    with index_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return index_path


def optional_dense_dependencies_available() -> bool:
    return optional_qdrant_local_dependencies_available()


def _dense_tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower().replace("_", " ")) if token}


def _jaccard_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


__all__ = [
    "DenseRetriever",
    "FakeRetriever",
    "LexicalRetriever",
    "LocalDenseRetriever",
    "QdrantFastEmbedRetriever",
    "QdrantLocalRetriever",
    "QdrantServerRetriever",
    "RetrievedChunk",
    "Retriever",
    "chunk_text",
    "ingest_documents",
    "optional_dense_dependencies_available",
]
