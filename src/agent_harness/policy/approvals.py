from __future__ import annotations

from agent_harness.schemas import RunProviderRecord


def provider_use_approval(provider: RunProviderRecord, trust_action: str) -> tuple[bool, str]:
    approval_required = trust_action == "approval_required"
    reason = "provider use allowed"
    if provider.trust_zone == "local_process" and provider.network:
        approval_required = True
        reason = "local_process with network boundary requires approval"
    elif approval_required:
        reason = f"{provider.trust_zone} requires approval"

    if provider.requires_approval:
        approval_required = True
        reason = "provider profile requires approval"
    return approval_required, reason
