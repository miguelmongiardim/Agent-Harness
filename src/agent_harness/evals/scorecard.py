from agent_harness.evals.schema import EvalResult


def scorecard_status(results: list[EvalResult]) -> str:
    return "passed" if all(result.passed for result in results) else "failed"
