class HarnessError(RuntimeError):
    """Base exception for Agent Harness runtime failures."""


class UnsupportedAdapterError(HarnessError):
    """Raised when an optional runtime or provider adapter is selected before implementation."""
