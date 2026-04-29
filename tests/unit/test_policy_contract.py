from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.model.schema import RunProviderRecord
from agent_harness.policy import PolicyEngine
from agent_harness.policy.schema import PolicyProfile


def test_default_provider_input_matrix_and_non_widening_overrides(
    tmp_path: Path,
) -> None:
    assert DEFAULT_POLICY["schema_version"] == "policy.v2"
    assert "provider_input" in DEFAULT_POLICY
    assert "trust_zones" in DEFAULT_POLICY
    assert "approvals" in DEFAULT_POLICY
    assert "scanner" in DEFAULT_POLICY
    assert "template_capabilities" in DEFAULT_POLICY
    assert "migration" in DEFAULT_POLICY

    profile = PolicyProfile.model_validate(DEFAULT_POLICY)
    assert profile.schema_version == "policy.v2"
    assert profile.provider_input is not None
    assert profile.provider_input.rules == {
        "public": "allow",
        "generated": "allow_untrusted",
        "internal": "approval_required",
        "confidential": "deny",
        "restricted": "deny",
        "secret": "deny",
        "credential": "deny",
        "pii": "deny",
        "customer": "deny",
        "unknown": "deny",
    }
    assert profile.provider_input.hard_deny_sensitivities == [
        "secret",
        "credential",
        "pii",
        "customer",
    ]

    engine = PolicyEngine(tmp_path, profile)
    provider = RunProviderRecord(
        provider_profile_id="mock-default",
        transport="mock",
        trust_zone="mock",
        model="deterministic",
        endpoint_env="AGENT_HARNESS_MOCK_ENDPOINT",
        endpoint_identity="env:AGENT_HARNESS_MOCK_ENDPOINT",
        network=False,
    )

    expectations = {
        "public": ("allow", True, False),
        "generated": ("allow_untrusted", True, False),
        "internal": ("approval_required", True, True),
        "confidential": ("deny", False, False),
        "restricted": ("deny", False, False),
        "secret": ("deny", False, False),
        "credential": ("deny", False, False),
        "pii": ("deny", False, False),
        "customer": ("deny", False, False),
        "unknown": ("deny", False, False),
    }
    for sensitivity, expected in expectations.items():
        action, decision = engine.evaluate_provider_input(
            sensitivity, provider, path=f"{sensitivity}.txt"
        )
        assert (action, decision.allowed, decision.approval_required) == expected

    action, decision = engine.evaluate_provider_input(
        "public",
        provider,
        path="public.txt",
        denied_sensitivities={"public"},
    )
    assert action == "deny"
    assert not decision.allowed

    action, decision = engine.evaluate_provider_input(
        "internal",
        provider,
        path="internal.txt",
        denied_sensitivities={"confidential"},
    )
    assert action == "approval_required"
    assert decision.allowed
    assert decision.approval_required


def test_policy_contract_rejects_flat_legacy_alias_payload() -> None:
    policy = deepcopy(DEFAULT_POLICY)
    for section in (
        "trust_zones",
        "provider_input",
        "approvals",
        "scanner",
        "template_capabilities",
        "migration",
    ):
        policy.pop(section)
    policy.pop("profile_kind")
    policy.pop("documented")
    policy.pop("deliberate_selection_required")

    with pytest.raises(ValidationError):
        PolicyProfile.model_validate(policy)

    policy["schema_version"] = "policy.v1"
    assert PolicyProfile.model_validate(policy).schema_version == "policy.v1"


def test_looser_profiles_must_be_named_documented_and_deliberate() -> None:
    loose = deepcopy(DEFAULT_POLICY)
    loose["name"] = "permissive-provider-input"
    loose["profile_kind"] = "looser_than_default"
    loose["description"] = ""
    loose["documented"] = False

    with pytest.raises(ValidationError):
        PolicyProfile.model_validate(loose)

    loose["description"] = "Allows internal provider input for a deliberate test profile."
    loose["documented"] = True
    loose["deliberate_selection_required"] = False
    with pytest.raises(ValidationError):
        PolicyProfile.model_validate(loose)

    loose["deliberate_selection_required"] = True
    profile = PolicyProfile.model_validate(loose)
    assert profile.profile_kind == "looser_than_default"
