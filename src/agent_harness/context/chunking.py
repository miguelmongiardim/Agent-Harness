from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str
    path: str
    text: str
    score: float
    start_line: int = 1
    end_line: int = 1


def chunk_text(text: str, source_id: str, path: str, max_chars: int = 1200) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    current: list[str] = []
    current_len = 0
    start_line = 1
    for line_no, line in enumerate(text.splitlines(), start=1):
        if current and current_len + len(line) + 1 > max_chars:
            body = "\n".join(current)
            chunks.append(
                RetrievedChunk(source_id, path, body, 1.0, start_line, line_no - 1)
            )
            current = []
            current_len = 0
            start_line = line_no
        current.append(line)
        current_len += len(line) + 1
    if current:
        body = "\n".join(current)
        chunks.append(
            RetrievedChunk(source_id, path, body, 1.0, start_line, start_line + len(current) - 1)
        )
    return chunks
