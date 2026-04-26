from __future__ import annotations

import json
from pathlib import Path

from agent_harness.context.retrieval import LexicalRetriever


def test_lexical_retriever_is_deterministic(tmp_path: Path) -> None:
    index = tmp_path / "documents.jsonl"
    records = [
        {
            "source_id": "s2",
            "path": "b.md",
            "text": "beta add_numbers",
            "start_line": 1,
            "end_line": 1,
        },
        {
            "source_id": "s1",
            "path": "a.md",
            "text": "alpha add_numbers",
            "start_line": 1,
            "end_line": 1,
        },
    ]
    index.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    chunks = LexicalRetriever(index).retrieve(["add_numbers"], limit=2)

    assert [chunk.path for chunk in chunks] == ["a.md", "b.md"]
