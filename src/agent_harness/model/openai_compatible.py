from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_harness.core.exceptions import UnsupportedAdapterError


@dataclass(frozen=True)
class OpenAICompatibleRequest:
    model: str
    messages: list[dict[str, Any]] = field(default_factory=list)


def raise_live_openai_compatible_unavailable() -> None:
    raise UnsupportedAdapterError(
        "live openai-compatible transport is not implemented; use recorded fixtures"
    )
