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

Local dense fixture behavior is opt-in with `retrieval_backend: qdrant`.
Qdrant/FastEmbed dependency checks are used as the local optional-dependency
gate, but V2 does not expose production Qdrant server mode and does not use
remote embeddings. Missing optional dependencies produce doctor warnings and
run manifests fall back to lexical retrieval.

Retrieved content is evidence only. It does not override task specs, policy
profiles, approval requirements, or tool execution rules.

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
