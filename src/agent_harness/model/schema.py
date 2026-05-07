from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.policy.schema import ProviderInputRuleAction, Sensitivity
from agent_harness.schema_base import StrictModel
from agent_harness.tools.schema import ToolCall
from agent_harness.utils import now_utc

ProviderTransport = Literal["mock", "openai_compatible", "anthropic"]
TrustZone = Literal["mock", "local_process", "local_endpoint", "private_network", "hosted_provider"]
ProviderCallPhase = Literal["initial_actions", "next_actions"]
ProviderExecutionMode = Literal["mock", "recorded_fixture", "live_smoke"]
ProviderActionEnvelopeKind = Literal["actions", "refusal", "unsupported"]


class ProviderProfileConfig(StrictModel):
    provider_profile_id: str = Field(min_length=1)
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str = Field(min_length=1)
    endpoint_env: str
    network: bool
    requires_approval: bool = False
    api_key_env: str | None = None

    @field_validator("endpoint_env")
    @classmethod
    def validate_endpoint_env(cls, value: str) -> str:
        return _validate_env_var_name(value)

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_env_var_name(value)


class RunProviderRecord(StrictModel):
    schema_version: Literal["provider_record.v1"] = "provider_record.v1"
    provider_profile_id: str
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str
    endpoint_env: str
    endpoint_identity: str
    network: bool
    requires_approval: bool = False


class ProviderActionEnvelope(StrictModel):
    schema_version: Literal["provider_action_envelope.v1"] = "provider_action_envelope.v1"
    kind: ProviderActionEnvelopeKind
    actions: list[ToolCall] = Field(default_factory=list)
    refusal_reason: str | None = None
    unsupported_reason: str | None = None

    @model_validator(mode="after")
    def validate_envelope(self) -> ProviderActionEnvelope:
        if self.kind == "actions":
            if self.refusal_reason is not None or self.unsupported_reason is not None:
                raise ValueError("action envelopes cannot include refusal or unsupported reasons")
            return self
        if self.actions:
            raise ValueError("refusal and unsupported envelopes cannot include actions")
        if self.kind == "refusal":
            if not self.refusal_reason:
                raise ValueError("refusal envelopes require refusal_reason")
            if self.unsupported_reason is not None:
                raise ValueError("refusal envelopes cannot include unsupported_reason")
            return self
        if not self.unsupported_reason:
            raise ValueError("unsupported envelopes require unsupported_reason")
        if self.refusal_reason is not None:
            raise ValueError("unsupported envelopes cannot include refusal_reason")
        return self


class ProviderInputRecord(StrictModel):
    record_id: str
    manifest_item_id: str | None = None
    source_id: str
    chunk_id: str
    path: str | None = None
    sensitivity: Sensitivity
    effective_sensitivity: Sensitivity
    policy_action: ProviderInputRuleAction
    included: bool
    untrusted: bool = False
    redaction_status: Literal["none", "redacted", "reclassified"] = "none"
    redactions_applied: list[str] = Field(default_factory=list)
    trust_zone: TrustZone
    provider_profile_id: str
    approval_id: str | None = None
    policy_decision_id: str
    policy_reason: str
    text: str | None = None
    content_hash: str | None = None


class ProviderInputManifest(StrictModel):
    schema_version: Literal["provider_input.v1"] = "provider_input.v1"
    run_id: str
    task_id: str
    provider_profile_id: str
    trust_zone: TrustZone
    records: list[ProviderInputRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class ProviderCallAudit(StrictModel):
    schema_version: Literal["provider_call_audit.v1"] = "provider_call_audit.v1"
    audit_id: str
    run_id: str
    task_id: str
    provider_profile_id: str
    transport: ProviderTransport
    trust_zone: TrustZone
    model: str
    endpoint_identity: str
    network: bool
    phase: ProviderCallPhase
    mode: ProviderExecutionMode
    fixture_id: str | None = None
    approval_ids: list[str] = Field(default_factory=list)
    action_count: int = 0
    actions_hash: str
    provider_input_hash: str = ""
    action_envelope_hash: str = ""
    checkpoint_hash: str = ""
    prompt_hash: str = ""
    response_hash: str = ""
    redacted_prompt_artifact: str = ""
    redacted_response_artifact: str = ""
    redacted_prompt_summary: dict[str, str | int] = Field(default_factory=dict)
    redacted_response_summary: dict[str, str | int] = Field(default_factory=dict)
    latency_ms: int = Field(default=0, ge=0)
    token_metrics: dict[str, int] = Field(default_factory=dict)
    policy_decision_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class ProviderCallAuditManifest(StrictModel):
    schema_version: Literal["provider_calls.v1"] = "provider_calls.v1"
    run_id: str
    task_id: str
    provider_profile_id: str
    calls: list[ProviderCallAudit] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class ProviderUseApprovalBinding(StrictModel):
    schema_version: Literal["provider_use_approval_binding.v1"] = "provider_use_approval_binding.v1"
    provider_profile_id: str
    trust_zone: TrustZone
    model_id: str
    provider_input_hash: str
    policy_decision_id: str
    checkpoint_hash: str


def _validate_env_var_name(value: str) -> str:
    if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value):
        raise ValueError("env var names must match [A-Z_][A-Z0-9_]*")
    return value
