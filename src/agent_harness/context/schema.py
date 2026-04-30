from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from agent_harness.policy.schema import Sensitivity
from agent_harness.schema_base import StrictModel
from agent_harness.utils import normalize_relative_path, now_utc

RetrievalMethod = Literal["direct", "lexical", "dense", "both"]
RetrievalEvidenceMethod = Literal["lexical", "dense"]


class ContextSource(StrictModel):
    source_id: str
    kind: Literal["file", "ingested_doc", "retrieval", "skill", "orchestration_handoff"]
    path: str | None = None
    uri: str | None = None
    content_hash: str
    sensitivity: Sensitivity = "public"
    policy_decision_id: str
    skill_id: str | None = None
    skill_version: str | None = None
    skill_source: str | None = None
    skill_hash: str | None = None
    handoff_id: str | None = None
    orchestration_id: str | None = None
    upstream_child_id: str | None = None
    upstream_run_id: str | None = None


class ContextChunk(StrictModel):
    chunk_id: str
    source_id: str
    text: str
    content_hash: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    score: float = Field(default=1.0, ge=0.0)
    sensitivity: Sensitivity = "public"


class RetrievalProvenance(StrictModel):
    method: RetrievalEvidenceMethod
    score: float = Field(default=0.0, ge=0.0)


class DenseRetrievalMetadata(StrictModel):
    backend: str
    model: str
    version: str


class RetrievalBackendManifest(StrictModel):
    schema_version: Literal["retrieval_backend.v1", "retrieval_backend.v2"] = "retrieval_backend.v2"
    requested_backend: Literal["fake", "lexical", "qdrant", "dense", "hybrid"]
    active_backend: str
    backend: str
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    embedding_model_cache_path: str | None = None
    index_id: str | None = None
    index_path: str | None = None
    qdrant_collection: str | None = None
    qdrant_storage_path: str | None = None
    qdrant_endpoint: str | None = None
    fallback_status: Literal["not_required", "used"] = "not_required"
    fallback_reason: str | None = None
    diagnostics: list[str] = Field(default_factory=list)
    remote_embeddings: bool = False


class RetrievalIndexSource(StrictModel):
    path: str
    content_hash: str
    chunk_ids: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_relative_path(value.strip())


class RetrievalIndexChunk(StrictModel):
    chunk_id: str
    source_id: str
    path: str
    content_hash: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return normalize_relative_path(value.strip())


class RetrievalIndexManifest(StrictModel):
    schema_version: Literal["retrieval_index.v1"] = "retrieval_index.v1"
    index_id: str
    index_path: str
    backend: Literal["lexical", "dense", "hybrid"]
    source_paths: list[str] = Field(default_factory=list)
    source_hashes: dict[str, str] = Field(default_factory=dict)
    sources: list[RetrievalIndexSource] = Field(default_factory=list)
    chunking_config: dict[str, int] = Field(default_factory=dict)
    chunks: list[RetrievalIndexChunk] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    chunk_hashes: dict[str, str] = Field(default_factory=dict)
    embedding_backend: str | None = None
    embedding_model: str | None = None
    embedding_model_version: str | None = None
    embedding_model_cache_path: str | None = None
    agent_harness_version: str
    created_at: datetime = Field(default_factory=now_utc)
    retrieval_config_hash: str
    qdrant_collection: str | None = None
    qdrant_storage_path: str | None = None
    qdrant_endpoint: str | None = None
    remote_embeddings: bool = False

    @field_validator("index_path")
    @classmethod
    def validate_index_path(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("source_paths")
    @classmethod
    def validate_source_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]


class RetrievalScorecardQuery(StrictModel):
    query_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_chunks: list[str] = Field(min_length=1)
    allowed_sensitivities: list[Sensitivity] = Field(min_length=1)


def _default_retrieval_scorecard_modes() -> list[Literal["lexical", "dense", "hybrid"]]:
    return ["lexical", "dense", "hybrid"]


class RetrievalScorecardFixture(StrictModel):
    schema_version: Literal["retrieval_scorecard_fixture.v1"] = "retrieval_scorecard_fixture.v1"
    queries: list[RetrievalScorecardQuery] = Field(min_length=1)
    compared_modes: list[Literal["lexical", "dense", "hybrid"]] = Field(
        default_factory=_default_retrieval_scorecard_modes,
        min_length=1,
    )
    min_precision_at_k: float = Field(default=0.0, ge=0.0, le=1.0)
    min_recall_at_k: float = Field(default=1.0, ge=0.0, le=1.0)


class ContextManifestItem(StrictModel):
    item_id: str
    source_id: str
    chunk_id: str
    source_kind: Literal["file", "retrieval", "skill", "orchestration_handoff"]
    path: str | None = None
    content_hash: str | None = None
    text: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    sensitivity: Sensitivity = "public"
    retrieval_method: RetrievalMethod
    provenance: list[RetrievalProvenance] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    policy_allowed: bool
    policy_decision_id: str
    policy_reason: str
    skill_id: str | None = None
    skill_version: str | None = None
    skill_source: str | None = None
    skill_hash: str | None = None
    inclusion_mode: Literal["task_required", "template_recommended"] | None = None
    handoff_id: str | None = None
    orchestration_id: str | None = None
    upstream_child_id: str | None = None
    upstream_run_id: str | None = None


class ContextManifest(StrictModel):
    schema_version: Literal["context_manifest.v1", "context_manifest.v2"] = "context_manifest.v2"
    manifest_id: str
    run_id: str
    task_id: str
    sources: list[ContextSource] = Field(default_factory=list)
    chunks: list[ContextChunk] = Field(default_factory=list)
    items: list[ContextManifestItem] = Field(default_factory=list)
    rejected_items: list[ContextManifestItem] = Field(default_factory=list)
    dense_retrieval: DenseRetrievalMetadata | None = None
    retrieval: RetrievalBackendManifest | None = None
    created_at: datetime = Field(default_factory=now_utc)
