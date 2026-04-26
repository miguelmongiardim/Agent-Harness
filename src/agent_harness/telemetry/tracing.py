from agent_harness.utils import stable_id


def trace_id(*parts: object) -> str:
    return stable_id("trace", *parts)
