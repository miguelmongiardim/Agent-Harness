from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ContextChunk,
    ContextManifest,
    ContextManifestItem,
    ContextSource,
    DenseRetrievalMetadata,
    PolicyDecision,
    RetrievalProvenance,
    TaskSpec,
)
from agent_harness.utils import sha256_text, stable_id


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    path: str
    text: str
    score: float
    start_line: int = 1
    end_line: int = 1


@dataclass(frozen=True)
class ContextBuildResult:
    manifest: ContextManifest
    retrieval_decisions: list[tuple[str, PolicyDecision]]


class Retriever(Protocol):
    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        ...


class DenseRetriever(Retriever, Protocol):
    def metadata(self) -> DenseRetrievalMetadata:
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
            import fastembed  # type: ignore[import-not-found]  # noqa: F401
            import qdrant_client  # type: ignore[import-not-found]  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("qdrant-client and fastembed are optional V0 dependencies") from exc

    def retrieve(self, queries: list[str], limit: int = 5) -> list[RetrievedChunk]:
        del queries, limit
        raise RuntimeError("Qdrant/FastEmbed retrieval is smoke-only in V0")


class LocalDenseRetriever:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def metadata(self) -> DenseRetrievalMetadata:
        return DenseRetrievalMetadata(
            backend="local_token_similarity",
            model="token-set",
            version="v1",
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
    lexical_retriever: Retriever,
    dense_retriever: DenseRetriever | None = None,
) -> ContextBuildResult:
    sources: dict[str, ContextSource] = {}
    chunks: list[ContextChunk] = []
    items: list[ContextManifestItem] = []
    rejected_items: list[ContextManifestItem] = []
    retrieval_decisions: list[tuple[str, PolicyDecision]] = []
    budget = policy.profile.max_context_bytes
    used = 0

    for target in task.target_paths:
        decision = policy.evaluate_context_source(target)
        path = project_root / target
        if not path.exists() or not path.is_file():
            continue
        sensitivity = policy.classify_path(target)
        if not decision.allowed:
            rejected_items.append(
                _manifest_item(
                    source_id=stable_id("source", target, "rejected"),
                    chunk_id=stable_id("chunk", target, "rejected"),
                    source_kind="file",
                    path=target,
                    content_hash=None,
                    text=None,
                    start_line=1,
                    end_line=1,
                    sensitivity=sensitivity,
                    retrieval_method="direct",
                    provenance=[],
                    scores={},
                    decision=decision,
                )
            )
            continue
        text = path.read_text(encoding="utf-8")
        redacted, _ = policy.redact_text(text)
        source_id = stable_id("source", target, sha256_text(text))
        sources[source_id] = ContextSource(
            source_id=source_id,
            kind="file",
            path=target,
            content_hash=sha256_text(text),
            sensitivity=sensitivity,  # type: ignore[arg-type]
            policy_decision_id=decision.decision_id,
        )
        for retrieved in chunk_text(redacted, source_id, target):
            if used + len(retrieved.text) > budget:
                break
            chunk = _manifest_chunk(retrieved, sensitivity)
            chunks.append(chunk)
            items.append(
                _manifest_item(
                    source_id=source_id,
                    chunk_id=chunk.chunk_id,
                    source_kind="file",
                    path=target,
                    content_hash=chunk.content_hash,
                    text=retrieved.text,
                    start_line=retrieved.start_line,
                    end_line=retrieved.end_line,
                    sensitivity=sensitivity,
                    retrieval_method="direct",
                    provenance=[],
                    scores={},
                    decision=decision,
                )
            )
            used += len(retrieved.text)

    candidate_map: dict[tuple[str, int, int], _MergedRetrievedChunk] = {}
    for retrieved in lexical_retriever.retrieve(task.context_queries, limit=5):
        _merge_candidate(candidate_map, retrieved, "lexical")
    dense_metadata = dense_retriever.metadata() if dense_retriever is not None else None
    if dense_retriever is not None:
        for retrieved in dense_retriever.retrieve(task.context_queries, limit=5):
            _merge_candidate(candidate_map, retrieved, "dense")

    for merged in sorted(
        candidate_map.values(),
        key=lambda candidate: (-candidate.rank_score, candidate.path, candidate.start_line),
    ):
        decision = policy.evaluate_context_source(merged.path)
        retrieval_decisions.append((merged.path, decision))
        if not decision.allowed:
            rejected_items.append(_merged_candidate_item(merged, policy, decision, text=None))
            continue
        redacted, _ = policy.redact_text(merged.text)
        if used + len(redacted) > budget:
            break
        source_id = merged.source_id
        sensitivity = policy.classify_path(merged.path)
        sources.setdefault(
            source_id,
            ContextSource(
                source_id=source_id,
                kind="retrieval",
                path=merged.path,
                content_hash=sha256_text(redacted),
                sensitivity=sensitivity,  # type: ignore[arg-type]
                policy_decision_id=decision.decision_id,
            ),
        )
        chunk = _manifest_chunk(
            RetrievedChunk(
                source_id=source_id,
                path=merged.path,
                text=redacted,
                score=merged.rank_score,
                start_line=merged.start_line,
                end_line=merged.end_line,
            ),
            sensitivity,
        )
        chunks.append(chunk)
        items.append(
            _merged_candidate_item(
                merged,
                policy,
                decision,
                text=redacted,
                content_hash=chunk.content_hash,
                chunk_id=chunk.chunk_id,
            )
        )
        used += len(redacted)

    return ContextBuildResult(
        manifest=ContextManifest(
            manifest_id=stable_id(
                "manifest",
                run_id,
                task.task_id,
                [item.item_id for item in items],
                [item.item_id for item in rejected_items],
            ),
            run_id=run_id,
            task_id=task.task_id,
            sources=list(sources.values()),
            chunks=chunks,
            items=items,
            rejected_items=rejected_items,
            dense_retrieval=dense_metadata,
        ),
        retrieval_decisions=retrieval_decisions,
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


@dataclass
class _MergedRetrievedChunk:
    path: str
    text: str
    start_line: int
    end_line: int
    source_ids: dict[Literal["lexical", "dense"], str] = field(default_factory=dict)
    scores: dict[Literal["lexical", "dense"], float] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return self.source_ids.get("lexical") or self.source_ids.get("dense") or stable_id(
            "source", self.path, sha256_text(self.text)
        )

    @property
    def retrieval_method(self) -> Literal["lexical", "dense", "both"]:
        if set(self.scores) == {"lexical", "dense"}:
            return "both"
        if "dense" in self.scores:
            return "dense"
        return "lexical"

    @property
    def rank_score(self) -> float:
        return max(self.scores.values(), default=0.0)

    def provenance(self) -> list[RetrievalProvenance]:
        entries: list[RetrievalProvenance] = []
        for method in ("lexical", "dense"):
            score = self.scores.get(method)
            if score is None:
                continue
            entries.append(RetrievalProvenance(method=method, score=score))
        return entries


def _merge_candidate(
    candidates: dict[tuple[str, int, int], _MergedRetrievedChunk],
    retrieved: RetrievedChunk,
    method: Literal["lexical", "dense"],
) -> None:
    key = (retrieved.path, retrieved.start_line, retrieved.end_line)
    existing = candidates.get(key)
    if existing is None:
        candidates[key] = _MergedRetrievedChunk(
            path=retrieved.path,
            text=retrieved.text,
            start_line=retrieved.start_line,
            end_line=retrieved.end_line,
            source_ids={method: retrieved.source_id},
            scores={method: float(retrieved.score)},
        )
        return
    existing.source_ids.setdefault(method, retrieved.source_id)
    existing.scores[method] = max(existing.scores.get(method, 0.0), float(retrieved.score))


def _merged_candidate_item(
    candidate: _MergedRetrievedChunk,
    policy: PolicyEngine,
    decision: PolicyDecision,
    *,
    text: str | None,
    content_hash: str | None = None,
    chunk_id: str | None = None,
) -> ContextManifestItem:
    return _manifest_item(
        source_id=candidate.source_id,
        chunk_id=chunk_id
        or stable_id("chunk", candidate.source_id, candidate.start_line, "rejected"),
        source_kind="retrieval",
        path=candidate.path,
        content_hash=content_hash,
        text=text,
        start_line=candidate.start_line,
        end_line=candidate.end_line,
        sensitivity=policy.classify_path(candidate.path),
        retrieval_method=candidate.retrieval_method,
        provenance=candidate.provenance(),
        scores={method: score for method, score in candidate.scores.items()},
        decision=decision,
    )


def _manifest_item(
    *,
    source_id: str,
    chunk_id: str,
    source_kind: Literal["file", "retrieval"],
    path: str | None,
    content_hash: str | None,
    text: str | None,
    start_line: int,
    end_line: int,
    sensitivity: str,
    retrieval_method: Literal["direct", "lexical", "dense", "both"],
    provenance: list[RetrievalProvenance],
    scores: dict[str, float],
    decision: PolicyDecision,
) -> ContextManifestItem:
    return ContextManifestItem(
        item_id=stable_id(
            "manifest-item",
            source_id,
            chunk_id,
            retrieval_method,
            decision.decision_id,
        ),
        source_id=source_id,
        chunk_id=chunk_id,
        source_kind=source_kind,
        path=path,
        content_hash=content_hash,
        text=text,
        start_line=start_line,
        end_line=end_line,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        retrieval_method=retrieval_method,
        provenance=provenance,
        scores=scores,
        policy_allowed=decision.allowed,
        policy_decision_id=decision.decision_id,
        policy_reason=decision.reason,
    )


def _dense_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", text.lower().replace("_", " "))
        if token
    }


def _jaccard_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
