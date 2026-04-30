from __future__ import annotations

from agent_harness.policy.schema import OrchestrationPolicyContract, PolicyProfile


class OrchestrationPolicyError(RuntimeError):
    pass


def require_orchestration_policy(profile: PolicyProfile) -> OrchestrationPolicyContract:
    policy = profile.orchestration
    if policy is None:
        raise OrchestrationPolicyError(
            "policy.v2.orchestration is missing; explicit orchestration policy is required"
        )
    if not policy.enabled:
        raise OrchestrationPolicyError("policy.v2.orchestration is disabled")
    return policy
