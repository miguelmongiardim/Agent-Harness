from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from agent_harness.context.chunking import RetrievedChunk
from agent_harness.context.schema import RetrievalProvenance
from agent_harness.utils import sha256_text, stable_id


@dataclass
class MergedRetrievedChunk:
    path: str
    text: str
    start_line: int
    end_line: int
    source_ids: dict[Literal["lexical", "dense"], str] = field(default_factory=dict)
    scores: dict[Literal["lexical", "dense"], float] = field(default_factory=dict)

    @property
    def source_id(self) -> str:
        return (
            self.source_ids.get("lexical")
            or self.source_ids.get("dense")
            or stable_id("source", self.path, sha256_text(self.text))
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


def merge_candidate(
    candidates: dict[tuple[str, int, int], MergedRetrievedChunk],
    retrieved: RetrievedChunk,
    method: Literal["lexical", "dense"],
) -> None:
    key = (retrieved.path, retrieved.start_line, retrieved.end_line)
    existing = candidates.get(key)
    if existing is None:
        candidates[key] = MergedRetrievedChunk(
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
