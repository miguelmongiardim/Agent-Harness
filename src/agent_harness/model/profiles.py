from __future__ import annotations

import os

from agent_harness.schemas import PolicyProfile, ProviderProfileConfig


class ProviderProfileValidationError(ValueError):
    pass


def validate_provider_profile_for_use(
    profile: ProviderProfileConfig,
    policy: PolicyProfile,
) -> None:
    if profile.transport == "mock":
        _validate_mock_profile(profile)
        return

    endpoint = _required_env(profile.endpoint_env)
    if profile.api_key_env is None:
        raise ProviderProfileValidationError(
            f"provider profile {profile.provider_profile_id} requires api_key_env"
        )
    _required_env(profile.api_key_env)

    if endpoint.startswith("recorded://"):
        return

    if not profile.network:
        raise ProviderProfileValidationError(
            f"provider profile {profile.provider_profile_id} uses a live endpoint "
            "but network is false"
        )
    if os.environ.get("AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS") != "1":
        raise ProviderProfileValidationError(
            "live provider profiles require AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1"
        )
    trust_action = policy.provider_trust_policy.get(profile.trust_zone)
    if trust_action != "approval_required" or not profile.requires_approval:
        raise ProviderProfileValidationError(
            f"live provider profile {profile.provider_profile_id} requires "
            "approval-compatible policy"
        )


def _validate_mock_profile(profile: ProviderProfileConfig) -> None:
    if profile.trust_zone != "mock":
        raise ProviderProfileValidationError(
            f"mock provider profile {profile.provider_profile_id} must use trust_zone mock"
        )
    if profile.network:
        raise ProviderProfileValidationError(
            f"mock provider profile {profile.provider_profile_id} must set network false"
        )
    if profile.api_key_env is not None:
        raise ProviderProfileValidationError(
            f"mock provider profile {profile.provider_profile_id} cannot configure api_key_env"
        )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ProviderProfileValidationError(f"missing required env var: {name}")
    return value
