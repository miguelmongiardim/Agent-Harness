from __future__ import annotations

import re


def compile_redaction_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def redact_text(text: str, patterns: list[re.Pattern[str]]) -> tuple[str, list[str]]:
    redactions: list[str] = []
    redacted = text
    for index, pattern in enumerate(patterns):
        if pattern.search(redacted):
            redacted = pattern.sub("[REDACTED]", redacted)
            redactions.append(f"redaction_pattern:{index}")
    return redacted, redactions
