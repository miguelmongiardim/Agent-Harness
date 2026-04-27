# Retrieval Quality Demo

This demo is the V5 local-first retrieval golden path. It shows a hybrid local
index, Qdrant-backed query evidence, scorecard comparison, and runtime context
assembly where denied or sensitive chunks stay out of accepted context.

Run from a checkout after installing retrieval extras:

```powershell
uv sync --extra retrieval
uv run agent-harness retrieval index build --index-id demo-retrieval --paths examples/retrieval_quality/docs --mode lexical
uv run agent-harness retrieval index build --index-id demo-retrieval --paths examples/retrieval_quality/docs --mode hybrid --dense-backend qdrant-local --overwrite
uv run agent-harness retrieval query demo-retrieval --query "refactor config loader policy" --mode hybrid --k 5
uv run agent-harness retrieval scorecard examples/retrieval_quality/scorecard.yaml --index-id demo-retrieval --k 5
uv run agent-harness release readiness
```

`config.v2.yaml` is the local-first runtime config for the demo. Copy it to
`agent-harness.yaml` in a scratch workspace when running `task.json`; it points
runtime context assembly at `demo-retrieval` with hybrid mode and local
FastEmbed/Qdrant evidence. `policy.v2.yaml` summarizes the policy split:
`default` is permissive enough to build the fixture index, while
`demo-runtime` rejects `docs/internal/denied-internal.md` by path and rejects
`docs/internal/secret-internal.md` by hard-denied sensitivity.

The document set intentionally includes:

- `docs/public/architecture.md`: exact lexical and dense match.
- `docs/public/coding-rules.md`: lexical-only match.
- `docs/public/semantic-note.md`: dense-only match.
- `docs/public/public-notes.md`: public supporting note.
- `docs/internal/denied-internal.md`: retrieved but path-denied at runtime.
- `docs/internal/secret-internal.md`: retrieved but hard-denied at runtime.

Expected example artifacts live under `expected/`; they are shape examples, not
generated release evidence. The generated artifacts should be created under
`.agent-harness/indexes/`, `.agent-harness/retrieval-scorecards/`, and
`.agent-harness/runs/` when you run the commands.

This demo does not use remote embeddings, hosted embedding providers, cloud
Qdrant, API-key-backed Qdrant endpoints, HTTPS Qdrant endpoints, or production
Qdrant server operation.
