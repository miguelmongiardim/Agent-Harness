# Context Packs And Retrieval

Current context handling favors inspectability over recall volume.

## Current Capabilities

Context manifests record:

- source path or source id
- source kind
- sensitivity classification
- content hash
- chunk hashes
- retrieval query
- policy decision evidence
- retrieval backend metadata, including requested backend, active backend,
  embedding model when local dense retrieval is active, index id, fallback
  reason, and `remote_embeddings: false`
- per-source retrieval scores and lexical/dense provenance when hybrid evidence
  is present

The default retriever is deterministic lexical retrieval over locally ingested
documents. A fake retriever is available for tests.

Lexical retrieval indexes can also be built explicitly with
`agent-harness retrieval index build --mode lexical`. The lifecycle commands
write local `retrieval_index.v1` manifests with stable source hashes, chunk
hashes, chunking config, retrieval config hash, and index paths; list, show,
and delete expose or remove those local artifacts.

Deterministic dense indexing and dense/hybrid query are available for fixture
and CI evidence through `--dense-backend deterministic`. The deterministic
backend uses local token-set scoring, requires no network access, requires no
model download, and records `retrieval_backend.v2` evidence with
`remote_embeddings: false`. It is test/fixture behavior, not a production
embedding backend.

When `agent-harness[retrieval]` is installed, dense and hybrid indexes can use
`--dense-backend qdrant-local`. This path executes FastEmbed locally and stores
persistent Qdrant local data under
`.agent-harness/indexes/<index-id>/qdrant` by default. The
`retrieval_index.v1` and `retrieval_backend.v2` evidence records the FastEmbed
model name, FastEmbed package version when available, model cache path, Qdrant
collection, Qdrant storage path, and `remote_embeddings: false`.

FastEmbed model initialization may acquire model files on the first local run.
Agent Harness passes `.agent-harness/models/fastembed` as the cache directory
for this optional path, so later runs can reuse the local model cache. Normal
tests do not require this path; the real FastEmbed/Qdrant smoke test skips
unless `agent-harness[retrieval]` is installed and
`AGENT_HARNESS_RUN_RETRIEVAL_OPTIONAL_TESTS=1` is set.

`--dense-backend qdrant-server` is available only as loopback developer
infrastructure. Its `config.v2` endpoint must use `localhost`, `127.0.0.1`, or
`::1`; cloud, HTTPS remote, API-key-backed, public IP, and private LAN Qdrant
endpoints remain rejected before document content is indexed or queried.
Loopback server manifests and query evidence record the endpoint, Qdrant
collection, FastEmbed model/version, cache path, and `remote_embeddings: false`.
If the loopback endpoint is unreachable, the CLI reports an actionable
diagnostic telling the user to start a loopback Qdrant server. Real server
smoke coverage skips unless `agent-harness[retrieval]` is installed and
`AGENT_HARNESS_RUN_QDRANT_SERVER_TESTS=1` is set.

A `config.v2` `retrieval.index_id` can route run-time context assembly through
a built retrieval index. Lexical, deterministic dense, qdrant-local,
qdrant-server, and hybrid modes preserve per-method scores, lexical/dense
provenance, backend/index evidence, and included/rejected manifest items.
Retrieved chunks are filtered by path policy and hard-deny sensitivity rules
before accepted context or provider input is created; rejected items omit source
text.

Local dense fixture behavior is opt-in with `retrieval_backend: qdrant`.
Qdrant/FastEmbed dependency checks are used as the local optional-dependency
gate, but V2 does not expose production Qdrant server mode and does not use
remote embeddings. Missing optional dependencies produce doctor warnings and
run manifests fall back to lexical retrieval.

Retrieved content is evidence only. It does not override task specs, policy
profiles, approval requirements, or tool execution rules.

`agent-harness retrieval scorecard` reads local
`retrieval_scorecard_fixture.v1` fixtures that define query ids, query text,
expected relevant chunks, and allowed sensitivity classes. The command reuses
the public retrieval query path to compare lexical, dense, and hybrid modes,
then writes `retrieval_scorecard.v1` under
`.agent-harness/retrieval-scorecards/` by default. Scorecards record
Precision@k, Recall@k, backend comparison status, per-query hits, misses, and
unexpected chunks. Retrieved result text is not copied into scorecard results.

A minimal JSON fixture looks like:

```json
{
  "schema_version": "retrieval_scorecard_fixture.v1",
  "queries": [
    {
      "query_id": "config-policy",
      "query": "config loader policy",
      "expected_chunks": ["docs/public/config.md"],
      "allowed_sensitivities": ["public"]
    }
  ]
}
```

## V5 Local-First Retrieval Hardening

The V5 implementation track is local-first retrieval hardening for v1.2.0. It
keeps lexical retrieval available in the base install while adding inspectable
local retrieval artifacts and quality evidence.

The V5 target scope is:

- lexical retrieval remains deterministic and available without optional
  dependencies
- deterministic dense embeddings are used for normal dense and hybrid tests
  without network access or model downloads
- FastEmbed is local-only optional behavior, with model acquisition and cache
  behavior documented when the retrieval extra is installed
- persistent local Qdrant storage uses repository-local index artifacts by
  default
- loopback-only Qdrant server support is developer infrastructure, not remote
  retrieval
- missing dense dependencies produce actionable diagnostics and follow lexical
  fallback behavior when configured
- retrieval scorecards compare lexical, dense, and hybrid modes with
  Precision@k and Recall@k
- context assembly keeps policy filtering, sensitivity classification, and
  provider-input checks as the boundary before retrieved chunks can be used

V5 treats retrieved text as untrusted evidence. Retrieval results do not widen
path policy, sensitivity policy, approval requirements, provider-input policy,
or tool permissions.

## Roadmap / Not Implemented

Cloud Qdrant, hosted embedding providers, remote embeddings, remote embedding
APIs, remote vector databases, API-key-backed Qdrant endpoints, HTTPS remote
Qdrant endpoints, production Qdrant server operation, deployment-scale
retrieval tuning, MCP retrieval workflows, API/UI surfaces, multi-agent
retrieval workflows, enterprise retrieval claims, and compliance-ready
retrieval claims are outside V5.
