from agent_harness.evals.schema import EvalInvariant


def all_invariants_passed(invariants: list[EvalInvariant]) -> bool:
    return all(invariant.passed for invariant in invariants)
