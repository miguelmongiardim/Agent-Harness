from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from agent_harness import __version__
from agent_harness.context.chunking import chunk_text
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    HarnessConfig,
    RetrievalIndexChunk,
    RetrievalIndexManifest,
    RetrievalIndexSource,
)
from agent_harness.utils import sha256_json, sha256_text, stable_id, write_json

LEXICAL_CHUNK_MAX_CHARS = 1200


def build_lexical_index(
    project_root: Path,
    config: HarnessConfig,
    policy: PolicyEngine,
    index_id: str,
    paths: list[str],
    *,
    overwrite: bool = False,
) -> RetrievalIndexManifest:
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

    manifest = RetrievalIndexManifest(
        index_id=index_id,
        index_path=documents_path.relative_to(project_root).as_posix(),
        backend="lexical",
        source_paths=[source.path for source in sources],
        source_hashes=source_hashes,
        sources=sources,
        chunking_config={"max_chars": LEXICAL_CHUNK_MAX_CHARS},
        chunks=chunks,
        chunk_ids=[chunk.chunk_id for chunk in chunks],
        chunk_hashes=chunk_hashes,
        agent_harness_version=__version__,
        retrieval_config_hash=sha256_json(
            {
                "mode": "lexical",
                "paths": paths,
                "retrieval": (
                    config.retrieval.model_dump(mode="json") if config.retrieval else None
                ),
                "retrieval_backend": config.retrieval_backend,
            }
        ),
        remote_embeddings=False,
    )
    write_json(index_dir / "retrieval_index.json", manifest.model_dump(mode="json"))
    return manifest


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
