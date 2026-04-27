# PRD: Agent Harness V5 Local-First Retrieval Hardening

## Problem Statement

Agent Harness v1.1.0 closes the V4 Provider Core track by validating provider
output, provider profiles, provider-input evidence, provider-call artifacts, and
deterministic provider-core evals. Retrieval remains the largest remaining drift
from the original controlled-agent conception.

The current retrieval path is useful and inspectable, but it is still centered
on deterministic lexical retrieval plus local dense fixture evidence. Reviewers
cannot yet build a persistent local dense index, inspect reproducible retrieval
index metadata, compare lexical, dense, and hybrid quality, or run a retrieval
scorecard that proves policy-filtered context assembly from a real local-first
retrieval subsystem.

Without V5, retrieval evidence remains hard to measure. The harness can show
that retrieved content is policy mediated, but it cannot yet prove that local
retrieval indexes are reproducible, inspectable, scored, and safe to use in
controlled agent workflows without sending document text to remote embedding
providers.

## Solution

V5 introduces a focused local-first retrieval hardening release for v1.2.0. It
keeps `config.v2`, preserves lexical retrieval for base installs, and adds
optional retrieval settings, index lifecycle commands, deterministic dense test
embeddings, persistent local Qdrant, optional loopback-only Qdrant server
support, hybrid retrieval, retrieval scorecards, and Qdrant-backed context
manifest evidence.

The primary user workflow is:

1. Configure local-first retrieval without introducing a new config schema
   version.
2. Build a lexical, deterministic dense, local Qdrant, or hybrid index from
   local files.
3. Inspect `retrieval_index.v1` and `retrieval_backend.v2` evidence.
4. Query an index in lexical, dense, or hybrid mode.
5. Run a retrieval scorecard that compares Precision@k and Recall@k across
   modes.
6. Use retrieval through context assembly, where every chunk is treated as
   untrusted evidence and must pass policy and sensitivity filtering before it
   can enter context, provider input, run execution, evals, or demos.

V5 deliberately avoids remote embeddings, hosted embedding providers, remote
vector databases, cloud Qdrant, production Qdrant server operations, MCP,
API/UI work, multi-agent workflows, and enterprise or compliance claims.

## Implemented in V5

The V5 target scope is local-first retrieval hardening:

- deterministic lexical retrieval in the base install
- optional `agent-harness[retrieval]` dependencies for FastEmbed and Qdrant
- local FastEmbed execution with documented model acquisition and cache behavior
- deterministic test embedding backend for normal dense retrieval tests
- persistent local Qdrant storage under `.agent-harness/indexes/` by default
- optional loopback-only Qdrant server support for developer infrastructure
- retrieval index lifecycle commands for build, list, show, delete, query, and
  scorecard
- reproducible retrieval index manifests
- retrieval backend resolution manifests
- retrieval quality scorecards with Precision@k and Recall@k
- hybrid lexical+dense retrieval with provenance in context manifests
- policy and sensitivity filtering before context assembly and provider input
- local retrieval demo under `examples/retrieval_quality/`
- release-readiness checks for retrieval docs, demo, scorecards, and remote
  retrieval denials

## Roadmap / Not implemented yet

The following are not part of V5:

- cloud Qdrant
- hosted embeddings
- remote embeddings
- remote embedding APIs
- remote vector databases
- API-key-backed Qdrant endpoints
- HTTPS remote Qdrant endpoints
- production Qdrant server mode
- MCP
- API or UI surfaces
- multi-agent workflows
- enterprise retrieval claims
- compliance-ready retrieval claims
- fully secure retrieval claims

## User Stories

1. As a developer, I want lexical retrieval to keep working in the base install,
   so that Agent Harness remains usable without optional dependencies.
2. As a developer, I want to install `agent-harness[retrieval]` and build a
   persistent local Qdrant index, so that I can test local dense retrieval
   without remote services.
3. As a reviewer, I want inspectable retrieval index manifests, so that I can
   verify source hashes, chunk hashes, backend settings, model evidence, and
   `remote_embeddings: false`.
4. As a contributor, I want deterministic dense retrieval tests that require no
   network and no model downloads, so that normal CI stays stable.
5. As a security-minded maintainer, I want remote embedding providers and cloud
   vector services rejected at configuration and CLI boundaries, so that
   document content cannot be sent to unsupported retrieval services.
6. As a reviewer, I want lexical, dense, and hybrid retrieval queries to expose
   provenance and per-method scores, so that I can understand why context was
   selected.
7. As an operator, I want denied and sensitive chunks filtered before context
   assembly and provider input, so that retrieval cannot bypass policy.
8. As a maintainer, I want retrieval scorecards with Precision@k and Recall@k,
   so that retrieval quality can be compared across modes and backends.
9. As a local developer, I want optional loopback-only Qdrant server support, so
   that I can test local server infrastructure without enabling remote Qdrant.
10. As a release reviewer, I want a local retrieval demo and release-readiness
    checks, so that V5 can be accepted from a clean checkout with retrieval
    extras installed.

## Behavioral Requirements

1. Existing `config.v2` files without V5 retrieval settings remain valid.
2. `config.v2` accepts backward-compatible optional retrieval settings for
   default mode, lexical settings, dense settings, Qdrant settings, and fallback
   policy.
3. `remote_embeddings: true` is rejected with a clear V5 validation error.
4. Hosted embedding providers, remote embedding APIs, remote vector databases,
   cloud Qdrant URLs, API-key-backed Qdrant endpoints, HTTPS remote Qdrant
   endpoints, public IP endpoints, and private LAN Qdrant endpoints are rejected
   in V5.
5. Base install supports lexical retrieval without Qdrant or FastEmbed.
6. Missing optional retrieval dependencies produce actionable diagnostics and
   follow configured lexical fallback behavior.
7. Tests requiring optional dependencies are marked and skipped unless those
   dependencies are installed or explicitly enabled.
8. `agent-harness retrieval index build` can build lexical and deterministic
   dense indexes without network access.
9. `agent-harness retrieval index build` can build a persistent local Qdrant
   index when retrieval extras are installed.
10. Index build fails when an index id already exists unless `--overwrite` is
    provided.
11. `--overwrite` removes or archives old index state cleanly before rebuilding.
12. `agent-harness retrieval index list`, `show`, and `delete` expose and manage
    local index metadata and storage.
13. `agent-harness retrieval index show <index-id>` displays source hashes,
    backend, model/version, chunking config, retrieval config hash, index path,
    and Qdrant collection when present.
14. `retrieval_index.v1` records schema version, index id, index path, backend,
    source paths, source hashes, chunking config, chunk ids, chunk hashes,
    embedding backend, embedding model, embedding model version, Agent Harness
    version, creation time, retrieval config hash, Qdrant collection, and
    `remote_embeddings: false`.
15. Rebuilding unchanged sources with unchanged retrieval config produces stable
    source and chunk metadata.
16. `retrieval_backend.v2` records requested backend, active backend, index id,
    index path, backend, embedding model/version, fallback status, fallback
    reason, diagnostics, and `remote_embeddings: false`.
17. `agent-harness retrieval query <index-id>` supports lexical, dense, and
    hybrid query modes with `--k`.
18. Unsupported retrieval modes or backends fail with clear diagnostics.
19. Deterministic dense embeddings are stable across runs, require no network,
    require no external model download, and are documented as test/fixture-only.
20. FastEmbed runs locally, records model name and version when available, and
    documents first-run model download and cache behavior.
21. `qdrant-local` stores persistent local index data under
    `.agent-harness/indexes/` by default.
22. `qdrant-server` accepts only loopback hosts: `localhost`, `127.0.0.1`, and
    `::1`.
23. Unreachable loopback Qdrant server endpoints produce actionable diagnostics.
24. Hybrid retrieval merges duplicate lexical and dense results and records
    whether each included item came from lexical, dense, or both.
25. Context manifests record lexical provenance, dense provenance, per-method
    scores, backend/index evidence, included items, rejected items, rejection
    reasons, sensitivity classes, and policy decisions.
26. Denied, sensitive, hard-denied, unknown, or policy-rejected chunks are
    filtered before context assembly, provider input, run execution, eval use,
    scorecards, and demos.
27. Retrieved text is always treated as untrusted evidence and never overrides
    policy, task specs, approvals, or tool execution rules.
28. `agent-harness retrieval scorecard` reads labeled query fixtures and writes
    `retrieval_scorecard.v1`.
29. `retrieval_scorecard.v1` records schema version, index id, `k`,
    compared modes, Precision@k, Recall@k, per-query results, expected chunks,
    hit chunks, missed chunks, unexpected chunks, and backend comparison.
30. Release readiness verifies the retrieval demo, scorecard evidence, docs,
    optional dependency diagnostics, and absence of default remote retrieval
    configuration.

## Implementation Decisions

- Keep `config.v2` as the public config schema. Add optional nested retrieval
  settings and preserve the legacy `retrieval_backend` field as a compatibility
  path unless implementation proves a real compatibility break.
- Introduce an explicit retrieval CLI group:
  `retrieval index build`, `retrieval index list`, `retrieval index show`,
  `retrieval index delete`, `retrieval query`, and `retrieval scorecard`.
- Keep deterministic lexical retrieval as the base-install retrieval backend.
- Use `agent-harness[retrieval]` as the optional dependency surface for Qdrant
  and FastEmbed.
- Add deterministic dense embeddings as a test and fixture backend, not as a
  production retrieval recommendation.
- Use FastEmbed only for local embedding execution. Document model acquisition,
  model cache location, model version evidence, and first-run download
  behavior.
- Add `qdrant-local` as the persistent local dense backend.
- Add `qdrant-server` only for loopback developer infrastructure and reject all
  non-loopback endpoints.
- Add retrieval artifact schemas `retrieval_index.v1`,
  `retrieval_backend.v2`, and `retrieval_scorecard.v1`.
- Keep context manifest assembly as the policy and sensitivity gate for
  provider-bound context.
- Keep retrieval results untrusted until context assembly accepts them.
- Extend release readiness rather than creating a separate release evidence
  command.
- Keep cloud retrieval, hosted embedding providers, remote vector databases, MCP,
  API/UI, and multi-agent behavior out of V5.

## Testing Decisions

- Start each implementation slice with one failing public-interface test, then
  implement the minimum behavior needed for green.
- Test retrieval configuration validation through config loading, CLI commands,
  and runtime behavior rather than private helpers only.
- Use deterministic dense embeddings for normal dense, hybrid, scorecard,
  manifest, fallback, and policy-filtering tests.
- Mark FastEmbed, persistent local Qdrant, and loopback Qdrant server tests as
  optional integration or smoke tests.
- Add unit tests for hard-deny config validation, loopback URL validation,
  manifest schema validation, retrieval config hash stability, Precision@k,
  Recall@k, deterministic embedding stability, dependency diagnostics, and
  index id collision behavior.
- Add integration tests for lexical index lifecycle, deterministic dense index
  lifecycle, hybrid context provenance, denied chunk rejection, sensitive chunk
  rejection, fallback diagnostics, list/show/delete behavior, and rebuild
  metadata stability.
- Add adversarial tests for remote embedding config rejection, cloud Qdrant
  endpoint rejection, API-key endpoint rejection, private LAN endpoint
  rejection, dense retrieval of sensitive chunks followed by policy rejection,
  lexical retrieval of denied paths followed by policy rejection, and unknown
  sensitivity rejection where policy requires it.
- Add e2e coverage for `examples/retrieval_quality/`, V5 golden path commands,
  retrieval scorecard generation, and release-readiness retrieval checks.
- Keep tests focused on public CLI/runtime/schema behavior, not fragile private
  function names.

## Out of Scope

- A new config schema version, unless a real compatibility break becomes
  unavoidable.
- Cloud Qdrant.
- Hosted embedding providers.
- Remote embeddings.
- Remote embedding APIs.
- Remote vector databases.
- API-key-backed Qdrant endpoints.
- HTTPS remote Qdrant endpoints.
- Production Qdrant server mode.
- MCP.
- API or UI surfaces.
- Multi-agent workflows.
- Enterprise retrieval claims.
- Compliance-ready retrieval claims.
- Fully secure retrieval claims.
- General retrieval benchmark platform beyond local scorecards.
- Remote model-provider changes beyond preserving existing provider-input
  safety.

## Further Notes

- The highest-risk boundary is retrieval bypassing policy by treating dense or
  lexical results as authoritative. V5 must keep retrieval as evidence only.
- The second highest-risk boundary is accidental remote data transfer through
  embeddings or vector storage. V5 must reject remote retrieval configuration
  early and record `remote_embeddings: false` in relevant artifacts.
- The deterministic dense backend is a testing strategy, not a product claim.
- FastEmbed model downloads are acceptable only as local model acquisition for
  an explicitly installed extra; normal CI must not depend on network access.
- V5 is accepted when a reviewer can run the local retrieval demo, inspect
  Qdrant-backed context manifests, compare lexical/dense/hybrid scorecards, and
  verify denied or sensitive chunks are filtered before context assembly.
