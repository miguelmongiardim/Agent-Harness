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

The default retriever is deterministic lexical retrieval over locally ingested
documents. A fake retriever is available for tests. Optional Qdrant/FastEmbed
support is isolated behind the retriever interface and falls back cleanly when
optional dependencies are unavailable.

Retrieved content is evidence only. It does not override task specs, policy
profiles, approval requirements, or tool execution rules.
