from __future__ import annotations

from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from agent_harness.model.schema import ProviderProfileConfig
from agent_harness.schema_base import StrictModel
from agent_harness.utils import normalize_relative_path


class RetrievalLexicalConfig(StrictModel):
    enabled: bool = True


class RetrievalDenseConfig(StrictModel):
    embedding_backend: Literal["deterministic", "fastembed"] = "deterministic"
    embedding_provider: str | None = None
    remote_embeddings: bool = False

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str | None) -> str | None:
        if value is None or value in {"deterministic", "fastembed"}:
            return value
        raise ValueError(
            "V5 local-first retrieval forbids hosted embedding providers; "
            "use deterministic or fastembed"
        )

    @field_validator("remote_embeddings")
    @classmethod
    def validate_remote_embeddings(cls, value: bool) -> bool:
        if value:
            raise ValueError("V5 local-first retrieval forbids remote_embeddings: true")
        return value


class RetrievalFallbackConfig(StrictModel):
    allow_lexical: bool = True


class RetrievalQdrantConfig(StrictModel):
    backend: Literal["qdrant-local", "qdrant-server"] = "qdrant-local"
    url: str | None = None
    api_key_env: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if hostname.endswith("cloud.qdrant.io"):
            raise ValueError("V5 local-first retrieval forbids cloud Qdrant URLs")
        if parsed.scheme.lower() == "https":
            raise ValueError("V5 local-first retrieval forbids remote HTTPS Qdrant endpoints")
        if not _is_loopback_qdrant_host(hostname):
            raise ValueError("V5 local-first retrieval forbids non-loopback Qdrant endpoints")
        return value

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, value: str | None) -> str | None:
        if value is not None:
            raise ValueError("V5 local-first retrieval forbids API-key-backed Qdrant endpoints")
        return value


class RetrievalConfig(StrictModel):
    default_mode: Literal["lexical", "dense", "hybrid"] = "lexical"
    index_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    lexical: RetrievalLexicalConfig = Field(default_factory=RetrievalLexicalConfig)
    dense: RetrievalDenseConfig = Field(default_factory=RetrievalDenseConfig)
    qdrant: RetrievalQdrantConfig = Field(default_factory=RetrievalQdrantConfig)
    fallback: RetrievalFallbackConfig = Field(default_factory=RetrievalFallbackConfig)


class TemplatesConfig(StrictModel):
    local_dirs: list[str] = Field(default_factory=list)

    @field_validator("local_dirs")
    @classmethod
    def validate_local_dirs(cls, values: list[str]) -> list[str]:
        normalized = [normalize_relative_path(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("templates.local_dirs values must be unique")
        return normalized


class SkillsConfig(StrictModel):
    local_dirs: list[str] = Field(default_factory=list)

    @field_validator("local_dirs")
    @classmethod
    def validate_local_dirs(cls, values: list[str]) -> list[str]:
        normalized = [_normalize_local_source_dir(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("skills.local_dirs values must be unique")
        return normalized


class HarnessConfig(StrictModel):
    schema_version: Literal["config.v1", "config.v2"]
    project_name: str
    artifact_root: str = ".agent-harness"
    default_policy: str = "default"
    retrieval_backend: Literal["fake", "lexical", "qdrant"] = "lexical"
    retrieval: RetrievalConfig | None = None
    template_catalog: str = "bundled"
    templates: TemplatesConfig = Field(default_factory=TemplatesConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    default_provider_profile: str | None = None
    provider_profiles: list[ProviderProfileConfig] = Field(default_factory=list)

    @field_validator("artifact_root")
    @classmethod
    def validate_artifact_root(cls, value: str) -> str:
        return normalize_relative_path(value)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> HarnessConfig:
        if self.schema_version == "config.v1":
            unsupported = []
            if self.default_provider_profile is not None or self.provider_profiles:
                unsupported.append("provider profiles")
            if self.retrieval is not None:
                unsupported.append("retrieval settings")
            if self.templates.local_dirs:
                unsupported.append("local template dirs")
            if self.skills.local_dirs:
                unsupported.append("local skill dirs")
            if unsupported:
                raise ValueError(f"config.v1 does not support {', '.join(unsupported)}")
            return self
        configured = [profile.provider_profile_id for profile in self.provider_profiles]
        if len(configured) != len(set(configured)):
            raise ValueError("provider_profile_id values must be unique")
        if (
            self.default_provider_profile is not None
            and self.default_provider_profile not in configured
        ):
            raise ValueError(
                "default_provider_profile must reference a configured provider profile"
            )
        return self


def _normalize_local_source_dir(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("~/") or normalized == "~":
        return normalized
    return normalize_relative_path(normalized)


def _is_loopback_qdrant_host(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False
