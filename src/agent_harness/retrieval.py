from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import ContextChunk, ContextManifest, ContextSource, TaskSpec
from agent_harness.utils import sha256_text, stable_id


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    path: str
    text: str
    score: float
    start_line: int = 1
    end_line: int = 1


class Retriever(Protocol):
    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        ...


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
            import fastembed  # noqa: F401
            import qdrant_client  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("qdrant-client and fastembed are optional V0 dependencies") from exc

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        del queries, limit
        raise RuntimeError("Qdrant/FastEmbed retrieval is smoke-only in V0")


def chunk_text(text: str, source_id: str, path: str, max_chars: int = 1200) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    current: list[str] = []
    current_len = 0
    start_line = 1
    for line_no, line in enumerate(text.splitlines(), start=1):
        if current and current_len + len(line) + 1 > max_chars:
            body = "\n".join(current)
            chunks.append(
                RetrievedChunk(source_id, path, body, 1.0, start_line, line_no - 1)
            )
            current = []
            current_len = 0
            start_line = line_no
        current.append(line)
        current_len += len(line) + 1
    if current:
        body = "\n".join(current)
        chunks.append(
            RetrievedChunk(source_id, path, body, 1.0, start_line, start_line + len(current) - 1)
        )
    return chunks


def ingest_documents(
    project_root: Path, artifact_root: Path, paths: list[str], policy: PolicyEngine
) -> Path:
    index_path = artifact_root / "indexes" / "documents.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for raw_path in paths:
        root = (project_root / raw_path).resolve()
        candidates = (
            [root]
            if root.is_file()
            else sorted(path for path in root.rglob("*") if path.is_file())
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


def build_context_manifest(
    project_root: Path,
    run_id: str,
    task: TaskSpec,
    policy: PolicyEngine,
    retriever: Retriever,
) -> ContextManifest:
    sources: dict[str, ContextSource] = {}
    chunks: list[ContextChunk] = []
    budget = policy.profile.max_context_bytes
    used = 0

    for target in task.target_paths:
        decision = policy.evaluate_context_source(target)
        if not decision.allowed:
            continue
        path = project_root / target
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        redacted, _ = policy.redact_text(text)
        source_id = stable_id("source", target, sha256_text(text))
        sources[source_id] = ContextSource(
            source_id=source_id,
            kind="file",
            path=target,
            content_hash=sha256_text(text),
            sensitivity=policy.classify_path(target),  # type: ignore[arg-type]
            policy_decision_id=decision.decision_id,
        )
        for retrieved in chunk_text(redacted, source_id, target):
            if used + len(retrieved.text) > budget:
                break
            chunks.append(_manifest_chunk(retrieved, policy.classify_path(target)))
            used += len(retrieved.text)

    for retrieved in retriever.retrieve(task.context_queries, limit=5):
        decision = policy.evaluate_context_source(retrieved.path)
        if not decision.allowed:
            continue
        if used + len(retrieved.text) > budget:
            break
        source_id = retrieved.source_id
        sources.setdefault(
            source_id,
            ContextSource(
                source_id=source_id,
                kind="retrieval",
                path=retrieved.path,
                content_hash=sha256_text(retrieved.text),
                sensitivity=policy.classify_path(retrieved.path),  # type: ignore[arg-type]
                policy_decision_id=decision.decision_id,
            ),
        )
        redacted, _ = policy.redact_text(retrieved.text)
        chunks.append(
            _manifest_chunk(
                RetrievedChunk(
                    source_id=retrieved.source_id,
                    path=retrieved.path,
                    text=redacted,
                    score=retrieved.score,
                    start_line=retrieved.start_line,
                    end_line=retrieved.end_line,
                ),
                policy.classify_path(retrieved.path),
            )
        )
        used += len(redacted)

    return ContextManifest(
        manifest_id=stable_id(
            "manifest", run_id, task.task_id, [chunk.chunk_id for chunk in chunks]
        ),
        run_id=run_id,
        task_id=task.task_id,
        sources=list(sources.values()),
        chunks=chunks,
    )


def _manifest_chunk(retrieved: RetrievedChunk, sensitivity: str) -> ContextChunk:
    return ContextChunk(
        chunk_id=stable_id(
            "chunk", retrieved.source_id, retrieved.start_line, sha256_text(retrieved.text)
        ),
        source_id=retrieved.source_id,
        text=retrieved.text,
        content_hash=sha256_text(retrieved.text),
        start_line=retrieved.start_line,
        end_line=retrieved.end_line,
        score=float(retrieved.score),
        sensitivity=sensitivity,  # type: ignore[arg-type]
    )
