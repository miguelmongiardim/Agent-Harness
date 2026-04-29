from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "ContextBuildResult",
    "DenseRetriever",
    "FakeRetriever",
    "LexicalRetriever",
    "LocalDenseRetriever",
    "QdrantFastEmbedRetriever",
    "RetrievedChunk",
    "Retriever",
    "build_context_manifest",
    "chunk_text",
    "ingest_documents",
]

_LAZY_EXPORTS = {
    "ContextBuildResult": ("agent_harness.context.builder", "ContextBuildResult"),
    "DenseRetriever": ("agent_harness.context.retrieval", "DenseRetriever"),
    "FakeRetriever": ("agent_harness.context.retrieval", "FakeRetriever"),
    "LexicalRetriever": ("agent_harness.context.retrieval", "LexicalRetriever"),
    "LocalDenseRetriever": ("agent_harness.context.retrieval", "LocalDenseRetriever"),
    "QdrantFastEmbedRetriever": (
        "agent_harness.context.retrieval",
        "QdrantFastEmbedRetriever",
    ),
    "RetrievedChunk": ("agent_harness.context.chunking", "RetrievedChunk"),
    "Retriever": ("agent_harness.context.retrieval", "Retriever"),
    "build_context_manifest": ("agent_harness.context.builder", "build_context_manifest"),
    "chunk_text": ("agent_harness.context.chunking", "chunk_text"),
    "ingest_documents": ("agent_harness.context.retrieval", "ingest_documents"),
}


if TYPE_CHECKING:
    from agent_harness.context.builder import ContextBuildResult, build_context_manifest
    from agent_harness.context.chunking import RetrievedChunk, chunk_text
    from agent_harness.context.retrieval import (
        DenseRetriever,
        FakeRetriever,
        LexicalRetriever,
        LocalDenseRetriever,
        QdrantFastEmbedRetriever,
        Retriever,
        ingest_documents,
    )


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, export_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name), export_name)
    globals()[name] = value
    return value
