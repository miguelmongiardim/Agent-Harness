from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import re
from contextlib import suppress
from pathlib import Path
from typing import Any

FASTEMBED_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class RetrievalOptionalDependencyError(RuntimeError):
    pass


def optional_qdrant_local_dependencies_available() -> bool:
    return (
        importlib.util.find_spec("qdrant_client") is not None
        and importlib.util.find_spec("fastembed") is not None
    )


def ensure_qdrant_local_dependencies() -> None:
    missing = [
        package_name
        for module_name, package_name in (
            ("fastembed", "fastembed"),
            ("qdrant_client", "qdrant-client"),
        )
        if importlib.util.find_spec(module_name) is None
    ]
    if missing:
        raise RetrievalOptionalDependencyError(
            "qdrant-local retrieval requires agent-harness[retrieval] optional "
            f"dependencies: missing {', '.join(missing)}"
        )


def qdrant_collection_name(index_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", index_id).strip("_").lower()
    return f"agent_harness_{normalized or 'index'}"


def fastembed_version() -> str:
    try:
        return importlib.metadata.version("fastembed")
    except importlib.metadata.PackageNotFoundError:
        module = importlib.import_module("fastembed")
        version = getattr(module, "__version__", None)
        return str(version) if version else "unknown"


def build_qdrant_local_collection(
    *,
    storage_path: Path,
    collection_name: str,
    records: list[dict[str, object]],
    model_name: str = FASTEMBED_DEFAULT_MODEL,
    cache_dir: Path | None = None,
) -> str:
    ensure_qdrant_local_dependencies()
    storage_path.mkdir(parents=True, exist_ok=True)
    texts = [str(record["text"]) for record in records]
    vectors = [
        _vector_to_floats(vector) for vector in _fastembed_model(model_name, cache_dir).embed(texts)
    ]
    vector_size = len(vectors[0]) if vectors else 1
    qdrant_client = importlib.import_module("qdrant_client")
    client = qdrant_client.QdrantClient(path=str(storage_path))
    try:
        _recreate_collection(qdrant_client, client, collection_name, vector_size)
        points = [
            qdrant_client.models.PointStruct(id=index + 1, vector=vector, payload=record)
            for index, (record, vector) in enumerate(zip(records, vectors, strict=True))
        ]
        if points:
            _upsert_points(client, collection_name, points)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    _write_storage_evidence(storage_path, collection_name, model_name, len(records))
    return fastembed_version()


def query_qdrant_local_collection(
    *,
    storage_path: Path,
    collection_name: str,
    query: str,
    model_name: str = FASTEMBED_DEFAULT_MODEL,
    cache_dir: Path | None = None,
    limit: int = 5,
) -> list[dict[str, object]]:
    ensure_qdrant_local_dependencies()
    vector = _vector_to_floats(next(_fastembed_model(model_name, cache_dir).embed([query])))
    qdrant_client = importlib.import_module("qdrant_client")
    client = qdrant_client.QdrantClient(path=str(storage_path))
    try:
        points = _query_points(client, collection_name, vector, limit)
        return [_point_to_result(point) for point in points]
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _fastembed_model(model_name: str, cache_dir: Path | None) -> Any:
    fastembed = importlib.import_module("fastembed")
    kwargs: dict[str, str] = {"model_name": model_name}
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        kwargs["cache_dir"] = str(cache_dir)
    return fastembed.TextEmbedding(**kwargs)


def _recreate_collection(
    qdrant_client: Any,
    client: Any,
    collection_name: str,
    vector_size: int,
) -> None:
    vectors_config = qdrant_client.models.VectorParams(
        size=vector_size,
        distance=qdrant_client.models.Distance.COSINE,
    )
    recreate = getattr(client, "recreate_collection", None)
    if callable(recreate):
        recreate(collection_name=collection_name, vectors_config=vectors_config)
        return
    delete = getattr(client, "delete_collection", None)
    if callable(delete):
        with suppress(Exception):
            delete(collection_name=collection_name)
    client.create_collection(collection_name=collection_name, vectors_config=vectors_config)


def _upsert_points(client: Any, collection_name: str, points: list[Any]) -> None:
    upsert = getattr(client, "upsert", None)
    if callable(upsert):
        upsert(collection_name=collection_name, points=points)
        return
    client.upload_points(collection_name=collection_name, points=points)


def _query_points(
    client: Any,
    collection_name: str,
    vector: list[float],
    limit: int,
) -> list[Any]:
    query_points = getattr(client, "query_points", None)
    if callable(query_points):
        try:
            response = query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                with_payload=True,
            )
        except TypeError:
            response = query_points(collection_name=collection_name, query=vector, limit=limit)
        points = getattr(response, "points", response)
        return list(points)
    search = getattr(client, "search", None)
    if callable(search):
        try:
            return list(
                search(
                    collection_name=collection_name,
                    query_vector=vector,
                    limit=limit,
                    with_payload=True,
                )
            )
        except TypeError:
            return list(search(collection_name=collection_name, query_vector=vector, limit=limit))
    raise RuntimeError("qdrant-client does not expose query_points or search")


def _point_to_result(point: Any) -> dict[str, object]:
    payload = getattr(point, "payload", None)
    if not isinstance(payload, dict):
        payload = {}
    score = getattr(point, "score", 0.0)
    return {
        "chunk_id": str(payload.get("chunk_id", "")),
        "source_id": str(payload.get("source_id", "")),
        "path": str(payload.get("path", "")),
        "text": str(payload.get("text", "")),
        "start_line": int(payload.get("start_line", 1)),
        "end_line": int(payload.get("end_line", 1)),
        "score": float(score),
    }


def _vector_to_floats(vector: Any) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


def _write_storage_evidence(
    storage_path: Path,
    collection_name: str,
    model_name: str,
    point_count: int,
) -> None:
    evidence_path = storage_path / "agent_harness_qdrant_local.json"
    evidence_path.write_text(
        json.dumps(
            {
                "collection_name": collection_name,
                "embedding_model": model_name,
                "point_count": point_count,
                "remote_embeddings": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
