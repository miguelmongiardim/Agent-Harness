from __future__ import annotations

from typing import Literal

from agent_harness.context.chunking import RetrievedChunk
from agent_harness.context.provenance import MergedRetrievedChunk
from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    ContextChunk,
    ContextManifestItem,
    PolicyDecision,
    RetrievalProvenance,
)
from agent_harness.utils import sha256_text, stable_id


def manifest_chunk(retrieved: RetrievedChunk, sensitivity: str) -> ContextChunk:
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


def merged_candidate_item(
    candidate: MergedRetrievedChunk,
    policy: PolicyEngine,
    decision: PolicyDecision,
    *,
    text: str | None,
    content_hash: str | None = None,
    chunk_id: str | None = None,
) -> ContextManifestItem:
    return manifest_item(
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


def manifest_item(
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
