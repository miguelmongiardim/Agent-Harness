from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_harness.context.chunking import RetrievedChunk, chunk_text
from agent_harness.context.manifest import manifest_chunk, manifest_item, merged_candidate_item
from agent_harness.context.provenance import MergedRetrievedChunk, merge_candidate
from agent_harness.context.retrieval import DenseRetriever, Retriever
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ContextChunk,
    ContextManifest,
    ContextManifestItem,
    ContextSource,
    PolicyDecision,
    RetrievalBackendManifest,
    TaskSpec,
)
from agent_harness.utils import sha256_text, stable_id


@dataclass(frozen=True)
class ContextBuildResult:
    manifest: ContextManifest
    retrieval_decisions: list[tuple[str, PolicyDecision]]


def build_context_manifest(
    project_root: Path,
    run_id: str,
    task: TaskSpec,
    policy: PolicyEngine,
    lexical_retriever: Retriever,
    dense_retriever: DenseRetriever | None = None,
    retrieval: RetrievalBackendManifest | None = None,
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
                manifest_item(
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
            chunk = manifest_chunk(retrieved, sensitivity)
            chunks.append(chunk)
            items.append(
                manifest_item(
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

    candidate_map: dict[tuple[str, int, int], MergedRetrievedChunk] = {}
    for retrieved in lexical_retriever.retrieve(task.context_queries, limit=5):
        merge_candidate(candidate_map, retrieved, "lexical")
    dense_metadata = dense_retriever.metadata() if dense_retriever is not None else None
    if dense_retriever is not None:
        for retrieved in dense_retriever.retrieve(task.context_queries, limit=5):
            merge_candidate(candidate_map, retrieved, "dense")

    for merged in sorted(
        candidate_map.values(),
        key=lambda candidate: (-candidate.rank_score, candidate.path, candidate.start_line),
    ):
        decision = policy.evaluate_context_source(merged.path)
        retrieval_decisions.append((merged.path, decision))
        if not decision.allowed:
            rejected_items.append(merged_candidate_item(merged, policy, decision, text=None))
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
        chunk = manifest_chunk(
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
            merged_candidate_item(
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
            retrieval=retrieval,
        ),
        retrieval_decisions=retrieval_decisions,
    )
