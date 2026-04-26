# Context Packs And Retrieval

Current context handling favors inspectability over recall volume.

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

Local dense fixture behavior is opt-in with `retrieval_backend: qdrant`.
Qdrant/FastEmbed dependency checks are used as the local optional-dependency
gate, but V2 does not expose production Qdrant server mode and does not use
remote embeddings. Missing optional dependencies produce doctor warnings and
run manifests fall back to lexical retrieval.

Retrieved content is evidence only. It does not override task specs, policy
profiles, approval requirements, or tool execution rules.

## Roadmap

Production Qdrant server operation, deployment-scale retrieval tuning, and
remote embedding providers are outside the current implementation.
