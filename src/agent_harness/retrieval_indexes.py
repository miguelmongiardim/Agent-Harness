from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Literal

from agent_harness import __version__
from agent_harness.config.schema import HarnessConfig
from agent_harness.context.chunking import chunk_text
from agent_harness.context.qdrant_local import (
    FASTEMBED_DEFAULT_MODEL,
    build_qdrant_local_collection,
    build_qdrant_server_collection,
    ensure_qdrant_local_dependencies,
    qdrant_collection_name,
    query_qdrant_local_collection,
    query_qdrant_server_collection,
)
from agent_harness.context.schema import (
    RetrievalBackendManifest,
    RetrievalIndexChunk,
    RetrievalIndexManifest,
    RetrievalIndexSource,
)
from agent_harness.policy import PolicyEngine
from agent_harness.utils import sha256_json, sha256_text, stable_id, write_json

LEXICAL_CHUNK_MAX_CHARS = 1200
RetrievalIndexMode = Literal["lexical", "dense", "hybrid"]
DenseBackend = Literal["deterministic", "qdrant-local", "qdrant-server"]


def build_retrieval_index(
    project_root: Path,
    config: HarnessConfig,
    policy: PolicyEngine,
    index_id: str,
    paths: list[str],
    *,
    mode: RetrievalIndexMode = "lexical",
    dense_backend: str | None = None,
    overwrite: bool = False,
) -> RetrievalIndexManifest:
    if mode in {"dense", "hybrid"} and dense_backend not in {
        "deterministic",
        "qdrant-local",
        "qdrant-server",
    }:
        raise ValueError(
            "dense and hybrid indexes require --dense-backend deterministic, "
            "qdrant-local, or qdrant-server"
        )
    if mode in {"dense", "hybrid"} and dense_backend in {"qdrant-local", "qdrant-server"}:
        ensure_qdrant_local_dependencies()
    project_root = project_root.resolve()
    _validate_index_id(index_id)
    artifact_root = project_root / config.artifact_root
    index_dir = artifact_root / "indexes" / index_id
    _prepare_index_dir(artifact_root, index_dir, overwrite=overwrite)

    records: list[dict[str, object]] = []
    sources: list[RetrievalIndexSource] = []
    chunks: list[RetrievalIndexChunk] = []
    source_hashes: dict[str, str] = {}
    chunk_hashes: dict[str, str] = {}

    for candidate in _source_candidates(project_root, paths):
        relative = candidate.relative_to(project_root).as_posix()
        decision = policy.evaluate_context_source(relative)
        if not decision.allowed:
            continue
        text = candidate.read_text(encoding="utf-8")
        source_hash = sha256_text(text)
        source_id = stable_id("source", relative, source_hash)
        source_chunk_ids: list[str] = []
        for chunk in chunk_text(text, source_id, relative, max_chars=LEXICAL_CHUNK_MAX_CHARS):
            chunk_hash = sha256_text(chunk.text)
            chunk_id = stable_id("chunk", source_id, chunk.start_line, chunk_hash)
            source_chunk_ids.append(chunk_id)
            chunk_hashes[chunk_id] = chunk_hash
            chunks.append(
                RetrievalIndexChunk(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    path=relative,
                    content_hash=chunk_hash,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                )
            )
            records.append(
                {
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "path": relative,
                    "text": chunk.text,
                    "text_hash": chunk_hash,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
            )
        source_hashes[relative] = source_hash
        sources.append(
            RetrievalIndexSource(
                path=relative,
                content_hash=source_hash,
                chunk_ids=source_chunk_ids,
            )
        )

    documents_path = index_dir / "documents.jsonl"
    index_dir.mkdir(parents=True, exist_ok=True)
    with documents_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    qdrant_collection: str | None = None
    qdrant_storage_path: str | None = None
    qdrant_endpoint: str | None = None
    embedding_model_cache_path: str | None = None
    embedding_model_version: str | None = None
    if dense_backend in {"qdrant-local", "qdrant-server"} and mode in {"dense", "hybrid"}:
        qdrant_collection = qdrant_collection_name(index_id)
        cache_dir = project_root / config.artifact_root / "models" / "fastembed"
        embedding_model_cache_path = cache_dir.relative_to(project_root).as_posix()
        try:
            if dense_backend == "qdrant-local":
                qdrant_storage = index_dir / "qdrant"
                embedding_model_version = build_qdrant_local_collection(
                    storage_path=qdrant_storage,
                    collection_name=qdrant_collection,
                    records=records,
                    model_name=FASTEMBED_DEFAULT_MODEL,
                    cache_dir=cache_dir,
                )
                qdrant_storage_path = qdrant_storage.relative_to(project_root).as_posix()
            else:
                qdrant_endpoint = _qdrant_server_endpoint(config)
                embedding_model_version = build_qdrant_server_collection(
                    endpoint=qdrant_endpoint,
                    collection_name=qdrant_collection,
                    records=records,
                    model_name=FASTEMBED_DEFAULT_MODEL,
                    cache_dir=cache_dir,
                )
        except Exception:
            if index_dir.exists():
                _remove_index_dir(artifact_root, index_dir)
            raise

    manifest = RetrievalIndexManifest(
        index_id=index_id,
        index_path=documents_path.relative_to(project_root).as_posix(),
        backend=mode,
        source_paths=[source.path for source in sources],
        source_hashes=source_hashes,
        sources=sources,
        chunking_config={"max_chars": LEXICAL_CHUNK_MAX_CHARS},
        chunks=chunks,
        chunk_ids=[chunk.chunk_id for chunk in chunks],
        chunk_hashes=chunk_hashes,
        embedding_backend=_embedding_backend(mode, dense_backend),
        embedding_model=_embedding_model(mode, dense_backend),
        embedding_model_version=(
            embedding_model_version
            if dense_backend in {"qdrant-local", "qdrant-server"}
            else ("baseline" if mode in {"dense", "hybrid"} else None)
        ),
        embedding_model_cache_path=embedding_model_cache_path,
        agent_harness_version=__version__,
        retrieval_config_hash=sha256_json(
            {
                "mode": mode,
                "dense_backend": dense_backend,
                "paths": paths,
                "retrieval": (
                    config.retrieval.model_dump(mode="json") if config.retrieval else None
                ),
                "retrieval_backend": config.retrieval_backend,
            }
        ),
        qdrant_collection=qdrant_collection,
        qdrant_storage_path=qdrant_storage_path,
        qdrant_endpoint=qdrant_endpoint,
        remote_embeddings=False,
    )
    write_json(index_dir / "retrieval_index.json", manifest.model_dump(mode="json"))
    return manifest


def build_lexical_index(
    project_root: Path,
    config: HarnessConfig,
    policy: PolicyEngine,
    index_id: str,
    paths: list[str],
    *,
    overwrite: bool = False,
) -> RetrievalIndexManifest:
    return build_retrieval_index(
        project_root,
        config,
        policy,
        index_id,
        paths,
        mode="lexical",
        overwrite=overwrite,
    )


def _embedding_backend(mode: RetrievalIndexMode, dense_backend: str | None) -> str | None:
    if mode not in {"dense", "hybrid"}:
        return None
    return "fastembed" if dense_backend in {"qdrant-local", "qdrant-server"} else "deterministic"


def _embedding_model(mode: RetrievalIndexMode, dense_backend: str | None) -> str | None:
    if mode not in {"dense", "hybrid"}:
        return None
    return (
        FASTEMBED_DEFAULT_MODEL
        if dense_backend in {"qdrant-local", "qdrant-server"}
        else "token-set"
    )


def _qdrant_server_endpoint(config: HarnessConfig) -> str:
    if config.retrieval is None or config.retrieval.qdrant.url is None:
        raise ValueError("qdrant-server retrieval requires retrieval.qdrant.url")
    return config.retrieval.qdrant.url


def _validate_index_id(index_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", index_id):
        raise ValueError("index id must use letters, numbers, dot, underscore, or dash")


def _prepare_index_dir(artifact_root: Path, index_dir: Path, *, overwrite: bool) -> None:
    if not index_dir.exists():
        return
    if not overwrite:
        raise ValueError(f"retrieval index already exists: {index_dir.name}")
    _remove_index_dir(artifact_root, index_dir)


def _remove_index_dir(artifact_root: Path, index_dir: Path) -> None:
    artifact_indexes = (artifact_root / "indexes").resolve()
    resolved = index_dir.resolve()
    try:
        resolved.relative_to(artifact_indexes)
    except ValueError as exc:
        raise ValueError("refusing to remove retrieval index outside artifact root") from exc
    shutil.rmtree(resolved)


def _source_candidates(project_root: Path, paths: list[str]) -> list[Path]:
    candidates: list[Path] = []
    for raw_path in paths:
        root = (project_root / raw_path).resolve()
        try:
            root.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"retrieval source escapes project: {raw_path}") from exc
        if not root.exists():
            raise ValueError(f"retrieval source not found: {raw_path}")
        candidates.extend(
            [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        )
    return sorted(dict.fromkeys(candidates))


def manifest_path(project_root: Path, config: HarnessConfig, index_id: str) -> Path:
    return project_root / config.artifact_root / "indexes" / index_id / "retrieval_index.json"


def list_indexes(project_root: Path, config: HarnessConfig) -> list[dict[str, object]]:
    indexes_root = project_root / config.artifact_root / "indexes"
    if not indexes_root.exists():
        return []
    listed: list[dict[str, object]] = []
    for manifest_file in sorted(indexes_root.glob("*/retrieval_index.json")):
        manifest = RetrievalIndexManifest.model_validate_json(
            manifest_file.read_text(encoding="utf-8")
        )
        listed.append(
            {
                "index_id": manifest.index_id,
                "backend": manifest.backend,
                "source_count": len(manifest.sources),
                "chunk_count": len(manifest.chunks),
                "manifest_path": manifest_file.relative_to(project_root).as_posix(),
            }
        )
    return listed


def load_index(project_root: Path, config: HarnessConfig, index_id: str) -> RetrievalIndexManifest:
    path = manifest_path(project_root, config, index_id)
    if not path.exists():
        raise ValueError(f"retrieval index not found: {index_id}")
    return RetrievalIndexManifest.model_validate_json(path.read_text(encoding="utf-8"))


def delete_index(project_root: Path, config: HarnessConfig, index_id: str) -> None:
    _validate_index_id(index_id)
    artifact_root = project_root / config.artifact_root
    index_dir = artifact_root / "indexes" / index_id
    if not index_dir.exists():
        raise ValueError(f"retrieval index not found: {index_id}")
    _remove_index_dir(artifact_root, index_dir)


def query_index(
    project_root: Path,
    config: HarnessConfig,
    index_id: str,
    query: str,
    *,
    mode: RetrievalIndexMode,
    limit: int,
) -> dict[str, object]:
    manifest = load_index(project_root, config, index_id)
    records = _index_records(project_root / manifest.index_path)
    if mode in {"dense", "hybrid"} and manifest.embedding_backend == "fastembed":
        results = _query_qdrant_index(project_root, manifest, records, query, mode, limit)
    elif mode in {"dense", "hybrid"} and manifest.embedding_backend != "deterministic":
        raise ValueError("dense and hybrid query require a deterministic or qdrant-local index")
    else:
        results = _query_records(records, query, mode=mode, limit=limit)
    return {
        "schema_version": "retrieval_query.v1",
        "index_id": index_id,
        "mode": mode,
        "query": query,
        "k": limit,
        "retrieval": _query_retrieval_backend(manifest, mode).model_dump(mode="json"),
        "results": results,
    }


def _index_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _query_qdrant_index(
    project_root: Path,
    manifest: RetrievalIndexManifest,
    records: list[dict[str, object]],
    query: str,
    mode: RetrievalIndexMode,
    limit: int,
) -> list[dict[str, object]]:
    if not manifest.qdrant_collection:
        raise ValueError("qdrant index is missing collection evidence")
    cache_dir = (
        project_root / manifest.embedding_model_cache_path
        if manifest.embedding_model_cache_path
        else None
    )
    if manifest.qdrant_endpoint is not None:
        qdrant_results = query_qdrant_server_collection(
            endpoint=manifest.qdrant_endpoint,
            collection_name=manifest.qdrant_collection,
            query=query,
            model_name=manifest.embedding_model or FASTEMBED_DEFAULT_MODEL,
            cache_dir=cache_dir,
            limit=limit,
        )
    else:
        if not manifest.qdrant_storage_path:
            raise ValueError("qdrant-local index is missing storage evidence")
        qdrant_results = query_qdrant_local_collection(
            storage_path=project_root / manifest.qdrant_storage_path,
            collection_name=manifest.qdrant_collection,
            query=query,
            model_name=manifest.embedding_model or FASTEMBED_DEFAULT_MODEL,
            cache_dir=cache_dir,
            limit=limit,
        )
    dense_results = [
        _query_result(
            result,
            "dense",
            _result_float(result, "score"),
        )
        for result in qdrant_results
        if _result_float(result, "score") > 0.0
    ]
    if mode == "dense":
        return dense_results[:limit]
    lexical_results = _query_records(records, query, mode="lexical", limit=limit)
    return _merge_query_results([*lexical_results, *dense_results], limit)


def _query_records(
    records: list[dict[str, object]],
    query: str,
    *,
    mode: RetrievalIndexMode,
    limit: int,
) -> list[dict[str, object]]:
    terms = _tokens(query)
    scored: list[tuple[float, str, int, dict[str, object]]] = []
    for record in records:
        text = str(record["text"])
        start_line = _record_int(record, "start_line")
        end_line = _record_int(record, "end_line")
        scores: dict[str, float] = {}
        if mode in {"lexical", "hybrid"}:
            lexical = _lexical_score(terms, text)
            if lexical > 0 or not terms:
                scores["lexical"] = lexical
        if mode in {"dense", "hybrid"}:
            dense = _dense_score(terms, text)
            if dense > 0:
                scores["dense"] = dense
        if not scores:
            continue
        retrieval_method = (
            "both" if set(scores) == {"lexical", "dense"} else next(iter(scores.keys()))
        )
        provenance = [{"method": method, "score": score} for method, score in scores.items()]
        result = {
            "chunk_id": str(record["chunk_id"]),
            "source_id": str(record["source_id"]),
            "path": str(record["path"]),
            "text": text,
            "start_line": start_line,
            "end_line": end_line,
            "retrieval_method": retrieval_method,
            "scores": scores,
            "provenance": provenance,
        }
        scored.append(
            (
                sum(scores.values()),
                str(record["path"]),
                start_line,
                result,
            )
        )
    return [
        item
        for _, _, _, item in sorted(
            scored,
            key=lambda entry: (-entry[0], entry[1], entry[2]),
        )[:limit]
    ]


def _query_result(
    result: dict[str, object],
    method: Literal["lexical", "dense"],
    score: float,
) -> dict[str, object]:
    return {
        "chunk_id": str(result["chunk_id"]),
        "source_id": str(result["source_id"]),
        "path": str(result["path"]),
        "text": str(result["text"]),
        "start_line": _result_int(result, "start_line"),
        "end_line": _result_int(result, "end_line"),
        "retrieval_method": method,
        "scores": {method: score},
        "provenance": [{"method": method, "score": score}],
    }


def _merge_query_results(
    results: list[dict[str, object]],
    limit: int,
) -> list[dict[str, object]]:
    merged: dict[tuple[str, int, int], dict[str, object]] = {}
    for result in results:
        key = (
            str(result["path"]),
            _result_int(result, "start_line"),
            _result_int(result, "end_line"),
        )
        existing = merged.get(key)
        result_scores = _result_scores(result)
        if existing is None:
            merged[key] = {
                **result,
                "scores": result_scores,
                "provenance": _result_provenance(result),
            }
            continue
        existing_scores = _result_scores(existing)
        for method, score in result_scores.items():
            existing_scores[str(method)] = max(
                float(existing_scores.get(str(method), 0.0)),
                float(score),
            )
        existing["scores"] = existing_scores
        existing["retrieval_method"] = (
            "both" if set(existing_scores) == {"lexical", "dense"} else next(iter(existing_scores))
        )
        existing["provenance"] = [
            {"method": method, "score": existing_scores[method]}
            for method in ("lexical", "dense")
            if method in existing_scores
        ]
    return sorted(
        merged.values(),
        key=lambda item: (
            -sum(_result_scores(item).values()),
            str(item["path"]),
            _result_int(item, "start_line"),
        ),
    )[:limit]


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


def _result_scores(result: dict[str, object]) -> dict[str, float]:
    value = result["scores"]
    if not isinstance(value, dict):
        raise ValueError("retrieval query scores must be a dictionary")
    return {str(method): _score_value(score) for method, score in value.items()}


def _score_value(value: object) -> float:
    if not isinstance(value, int | float | str):
        raise ValueError("retrieval query score must be numeric")
    return float(value)


def _result_provenance(result: dict[str, object]) -> list[object]:
    value = result["provenance"]
    if not isinstance(value, list):
        raise ValueError("retrieval query provenance must be a list")
    return list(value)


def _query_retrieval_backend(
    manifest: RetrievalIndexManifest,
    mode: RetrievalIndexMode,
) -> RetrievalBackendManifest:
    if mode == "lexical":
        return RetrievalBackendManifest(
            requested_backend="lexical",
            active_backend="lexical",
            backend="lexical",
            index_id=manifest.index_id,
            index_path=manifest.index_path,
            remote_embeddings=False,
        )
    if manifest.embedding_backend == "fastembed":
        is_server = manifest.qdrant_endpoint is not None
        return RetrievalBackendManifest(
            requested_backend=mode,
            active_backend=(
                f"qdrant_{'server' if is_server else 'local'}_"
                f"{'dense' if mode == 'dense' else 'hybrid'}"
            ),
            backend="qdrant-server" if is_server else "qdrant-local",
            embedding_model=manifest.embedding_model,
            embedding_model_version=manifest.embedding_model_version,
            embedding_model_cache_path=manifest.embedding_model_cache_path,
            index_id=manifest.index_id,
            index_path=manifest.index_path,
            qdrant_collection=manifest.qdrant_collection,
            qdrant_storage_path=manifest.qdrant_storage_path,
            qdrant_endpoint=manifest.qdrant_endpoint,
            remote_embeddings=False,
        )
    return RetrievalBackendManifest(
        requested_backend=mode,
        active_backend=("deterministic_dense" if mode == "dense" else "deterministic_hybrid"),
        backend="deterministic",
        embedding_model="token-set",
        embedding_model_version="baseline",
        index_id=manifest.index_id,
        index_path=manifest.index_path,
        remote_embeddings=False,
    )


def _lexical_score(terms: set[str], text: str) -> float:
    haystack = text.lower()
    return float(sum(1 for term in terms if term in haystack))


def _dense_score(terms: set[str], text: str) -> float:
    tokens = _tokens(text)
    if not terms or not tokens:
        return 0.0
    return len(terms & tokens) / len(terms | tokens)


def _tokens(text: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", text.lower().replace("_", " ")) if token}


def _record_int(record: dict[str, object], key: str) -> int:
    value = record[key]
    if not isinstance(value, int):
        raise ValueError(f"retrieval index record field must be int: {key}")
    return value
