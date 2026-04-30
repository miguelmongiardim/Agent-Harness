from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from agent_harness.schema_base import StrictModel
from agent_harness.security.schema import SecuritySeverity
from agent_harness.tools.schema import ToolName
from agent_harness.utils import normalize_relative_path, now_utc

TrustZone = Literal["mock", "local_process", "local_endpoint", "private_network", "hosted_provider"]
Sensitivity = Literal[
    "public",
    "internal",
    "confidential",
    "restricted",
    "secret",
    "pii",
    "customer",
    "credential",
    "generated",
    "unknown",
]
ProviderUseRuleAction = Literal["allow", "approval_required", "deny"]
ProviderInputRuleAction = Literal["allow", "allow_untrusted", "approval_required", "redact", "deny"]
OrchestrationExecutionMode = Literal["sequential"]
OrchestrationRolePolicyName = Literal["planner", "implementer", "reviewer", "tester"]


class SensitivityRule(StrictModel):
    pattern: str
    classification: Sensitivity


class ProviderTrustPolicyContract(StrictModel):
    rules: dict[TrustZone, ProviderUseRuleAction]


class ProviderInputPolicyContract(StrictModel):
    rules: dict[Sensitivity, ProviderInputRuleAction]
    hard_deny_sensitivities: list[Sensitivity] = Field(default_factory=list)
    redact_reclassify: dict[Sensitivity, Sensitivity] = Field(default_factory=dict)


class ApprovalPolicyContract(StrictModel):
    required_tools: list[ToolName] = Field(default_factory=list)


class ScannerPolicyContract(StrictModel):
    fail_threshold: SecuritySeverity = "high"
    external_reports: Literal["advisory", "disabled"] = "advisory"


class TemplateCapabilityPolicyContract(StrictModel):
    allowed_capabilities: list[str] = Field(default_factory=list)
    default_action: Literal["deny", "allow"] = "deny"


class MigrationPolicyContract(StrictModel):
    safe_writes: bool = True
    preserve_or_tighten: bool = True
    allow_loose_rewrites: bool = False


def _default_orchestration_roles() -> list[OrchestrationRolePolicyName]:
    return ["planner", "implementer", "reviewer", "tester"]


class OrchestrationPolicyContract(StrictModel):
    enabled: bool = False
    execution: OrchestrationExecutionMode = "sequential"
    allowed_roles: list[OrchestrationRolePolicyName] = Field(
        default_factory=_default_orchestration_roles
    )
    allow_nested: bool = False

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(
        cls, values: list[OrchestrationRolePolicyName]
    ) -> list[OrchestrationRolePolicyName]:
        if not values:
            raise ValueError("orchestration.allowed_roles must not be empty")
        if len(values) != len(set(values)):
            raise ValueError("orchestration.allowed_roles values must be unique")
        return values


def _default_allowed_context_classes() -> list[Sensitivity]:
    return ["public", "internal", "generated"]


class PolicyProfile(StrictModel):
    schema_version: Literal["policy.v1", "policy.v2"]
    name: str
    description: str = ""
    profile_kind: Literal["default", "stricter_than_default", "looser_than_default"] = "default"
    documented: bool = False
    deliberate_selection_required: bool = True
    trust_zones: ProviderTrustPolicyContract | None = None
    provider_input: ProviderInputPolicyContract | None = None
    approvals: ApprovalPolicyContract | None = None
    scanner: ScannerPolicyContract | None = None
    template_capabilities: TemplateCapabilityPolicyContract | None = None
    migration: MigrationPolicyContract | None = None
    orchestration: OrchestrationPolicyContract | None = None
    allowed_tools: list[ToolName] = Field(default_factory=list)
    read_roots: list[str] = Field(default_factory=lambda: ["."])
    write_roots: list[str] = Field(default_factory=list)
    deny_globs: list[str] = Field(default_factory=list)
    approval_required_tools: list[ToolName] = Field(default_factory=list)
    allowed_test_commands: list[list[str]] = Field(default_factory=list)
    allow_network: bool = False
    provider_trust_policy: dict[TrustZone, ProviderUseRuleAction] = Field(default_factory=dict)
    provider_input_policy: dict[Sensitivity, ProviderInputRuleAction] = Field(default_factory=dict)
    hard_deny_sensitivities: list[Sensitivity] = Field(default_factory=list)
    provider_input_redact_reclassify: dict[Sensitivity, Sensitivity] = Field(default_factory=dict)
    allowed_context_classes: list[Sensitivity] = Field(
        default_factory=_default_allowed_context_classes
    )
    max_context_bytes: int = Field(default=20000, ge=1024)
    security_fail_threshold: SecuritySeverity = "high"
    sensitivity_rules: list[SensitivityRule] = Field(default_factory=list)
    redaction_patterns: list[str] = Field(default_factory=list)

    @field_validator("read_roots", "write_roots")
    @classmethod
    def validate_roots(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]

    @model_validator(mode="before")
    @classmethod
    def hydrate_policy_contract_sections(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        hydrated = dict(data)
        if "provider_input_policy" in hydrated:
            provider_input = dict(hydrated.get("provider_input") or {})
            provider_input["rules"] = hydrated["provider_input_policy"]
            provider_input["hard_deny_sensitivities"] = hydrated.get("hard_deny_sensitivities", [])
            provider_input["redact_reclassify"] = hydrated.get(
                "provider_input_redact_reclassify", {}
            )
            hydrated["provider_input"] = provider_input
        if "provider_trust_policy" in hydrated:
            trust_zones = dict(hydrated.get("trust_zones") or {})
            trust_zones["rules"] = hydrated["provider_trust_policy"]
            hydrated["trust_zones"] = trust_zones
        if "approval_required_tools" in hydrated:
            approvals = dict(hydrated.get("approvals") or {})
            approvals["required_tools"] = hydrated["approval_required_tools"]
            hydrated["approvals"] = approvals
        if "security_fail_threshold" in hydrated:
            scanner = dict(hydrated.get("scanner") or {})
            scanner["fail_threshold"] = hydrated["security_fail_threshold"]
            hydrated["scanner"] = scanner
        return hydrated

    @model_validator(mode="after")
    def validate_policy_contract(self) -> PolicyProfile:
        if self.provider_input is not None:
            self.provider_input_policy = dict(self.provider_input.rules)
            self.hard_deny_sensitivities = list(self.provider_input.hard_deny_sensitivities)
            self.provider_input_redact_reclassify = dict(self.provider_input.redact_reclassify)
        if self.trust_zones is not None:
            self.provider_trust_policy = dict(self.trust_zones.rules)
        if self.approvals is not None:
            self.approval_required_tools = list(self.approvals.required_tools)
        if self.scanner is not None:
            self.security_fail_threshold = self.scanner.fail_threshold
        if self.schema_version == "policy.v2":
            missing = [
                name
                for name in (
                    "trust_zones",
                    "provider_input",
                    "approvals",
                    "scanner",
                    "template_capabilities",
                    "migration",
                )
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"policy.v2 missing required sections: {', '.join(missing)}")
        if self.profile_kind == "looser_than_default":
            if self.name == "default":
                raise ValueError("looser-than-default policy profiles must be named")
            if not self.description or not self.documented:
                raise ValueError("looser-than-default policy profiles must be documented")
            if not self.deliberate_selection_required:
                raise ValueError("looser-than-default policy profiles require deliberate selection")
        return self


class PolicyDecision(StrictModel):
    schema_version: Literal["policy_decision.v1"] = "policy_decision.v1"
    decision_id: str
    allowed: bool
    approval_required: bool = False
    reason: str
    matched_rules: list[str] = Field(default_factory=list)
    redactions_applied: list[str] = Field(default_factory=list)
    decided_at: datetime = Field(default_factory=now_utc)
