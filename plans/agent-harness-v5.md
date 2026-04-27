# Plan: Agent Harness V5 Local-First Retrieval Hardening

> Source PRD: [docs/prd-agent-harness-v5.md](../docs/prd-agent-harness-v5.md)

This plan has been implemented through the V5 TDD sessions. Acceptance boxes
remain checked only for behavior backed by tests, docs, or release evidence.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: preserve existing commands and add
  `agent-harness retrieval index build/list/show/delete`,
  `agent-harness retrieval query`, and `agent-harness retrieval scorecard`.
- **Config schema**: keep `config.v2`; add optional retrieval fields and keep the
  current `retrieval_backend` setting as a compatibility path.
- **Key models**: introduce `retrieval_index.v1`, `retrieval_backend.v2`, and
  `retrieval_scorecard.v1` as public artifact contracts.
- **Storage**: store local retrieval indexes and manifests under
  `.agent-harness/indexes/` by default; persistent Qdrant local storage remains
  under the workspace artifact root.
- **Runtime boundary**: retrieval returns candidate chunks and scores only;
  context assembly decides inclusion after policy and sensitivity checks.
- **Policy boundary**: retrieval cannot bypass path policy, sensitivity
  classification, redaction, provider-input policy, or approval requirements.
- **Embedding boundary**: FastEmbed is local-only; deterministic embeddings are
  test/fixture-only; remote embedding providers are rejected.
- **Qdrant boundary**: `qdrant-local` is persistent local storage;
  `qdrant-server` is optional loopback-only developer infrastructure.
- **Fallback model**: lexical retrieval remains deterministic, inspectable, and
  available when dense dependencies or indexes are unavailable.
- **Release boundary**: V5 targets v1.2.0 and stays limited to local-first
  retrieval hardening.

---

## Phase 0: Retrieval Scope Is Documented And Guarded

**User stories covered**

- Story 3: reviewer can inspect the intended retrieval boundary.
- Story 5: maintainer can verify remote retrieval is out of scope.
- Story 10: release reviewer can distinguish implemented behavior from roadmap.

**Observable behaviors**

- Retrieval docs identify V5 as local-first retrieval hardening.
- Docs distinguish V5 behavior from roadmap behavior.
- Docs checks fail when guarded retrieval phrases are claimed as implemented
  behavior outside roadmap sections.

**First RED test**

- `agent-harness docs check` passes while a doc claims cloud or remote retrieval
  as implemented V5 behavior.

### What to build

Add the V5 PRD, plan, retrieval docs, roadmap positioning, and README links.
Extend docs-check coverage only as needed to guard V5 retrieval scope claims.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v5.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v5.md` is a vertical-slice implementation plan.
- [x] `docs/context-retrieval.md` or the current context retrieval doc explains
      lexical retrieval, deterministic dense tests, FastEmbed local embeddings,
      persistent local Qdrant, loopback-only Qdrant server, fallback behavior,
      scorecards, and policy filtering.
- [x] `docs/roadmap.md` marks cloud and remote retrieval as future only.
- [x] `README.md` links to the retrieval demo once it exists.
- [x] Docs distinguish implemented V5 behavior from roadmap behavior.
- [x] Docs check passes.

### Out of scope

- Retrieval CLI implementation.
- Qdrant or FastEmbed code.
- Scorecard computation.

---

## Phase 1: Remote Retrieval Config Fails Before Use

**User stories covered**

- Story 1: base lexical retrieval remains valid.
- Story 5: unsupported remote retrieval is rejected clearly.
- Story 6: retrieval mode selection is explicit and inspectable.

**Observable behaviors**

- Existing `config.v2` files load unchanged.
- Valid local-first retrieval config loads.
- Remote embeddings and cloud/vector service settings fail before index build,
  query, run, demo, or eval.
- Missing optional retrieval dependencies produce actionable diagnostics and
  lexical fallback evidence when fallback is configured.

**First RED test**

- A `config.v2` file with `retrieval.dense.remote_embeddings: true` is accepted
  and later falls through to runtime behavior instead of failing validation.

### What to build

Extend `config.v2` with optional retrieval settings and hard-deny validation.
Thread backend resolution diagnostics through CLI and runtime entry points far
enough to prove invalid config cannot be used.

### Acceptance criteria

- [x] Existing `config.v2` files remain valid.
- [x] Valid V5 local-first retrieval config validates.
- [x] `remote_embeddings: true` fails with a clear V5 validation error.
- [x] Hosted embedding providers fail validation.
- [x] Cloud Qdrant URLs fail validation.
- [x] API-key-backed Qdrant endpoints fail validation.
- [x] Remote HTTPS Qdrant endpoints fail validation.
- [x] Private LAN and public IP Qdrant endpoints fail unless they are explicit
      loopback addresses allowed by a later phase.
- [x] Missing optional retrieval dependencies produce actionable diagnostics.
- [x] Optional-dependency tests are marked and skipped unless dependencies are
      installed.

### Out of scope

- Building persistent Qdrant indexes.
- Query scoring quality metrics.
- Loopback server querying.

---

## Phase 2: User Can Build And Inspect A Reproducible Lexical Index

**User stories covered**

- Story 1: lexical retrieval works in the base install.
- Story 3: reviewer can inspect retrieval index evidence.
- Story 10: release reviewer can verify local retrieval artifacts.

**Observable behaviors**

- A user can build a lexical index from local paths.
- A user can list, show, and delete the index.
- The index writes `retrieval_index.v1` with stable source and chunk evidence.
- Rebuild behavior is deterministic and collision-safe.

**First RED test**

- `agent-harness retrieval index build --mode lexical` has no public command or
  does not write an inspectable `retrieval_index.v1` manifest.

### What to build

Create the retrieval index lifecycle command path for lexical indexes. Use the
existing chunking and policy boundaries where practical, and keep the manifest
shape compatible with later dense and Qdrant backends.

### Acceptance criteria

- [x] `agent-harness retrieval index build --mode lexical` builds a local index.
- [x] `agent-harness retrieval index list` shows the created index.
- [x] `agent-harness retrieval index show <index-id>` displays source hashes,
      backend, chunking config, config hash, index path, and chunk metadata.
- [x] `agent-harness retrieval index delete <index-id>` removes lexical index
      metadata and safe local storage.
- [x] `retrieval_index.v1` records required reproducibility fields.
- [x] Index id collision fails unless `--overwrite` is provided.
- [x] `--overwrite` replaces old lexical index state cleanly.
- [x] Rebuild from unchanged sources produces stable source and chunk metadata.
- [x] Base install needs no Qdrant or FastEmbed.

### Out of scope

- Dense embedding generation.
- Hybrid merging.
- Scorecards.

---

## Phase 3: User Can Query Deterministic Dense And Hybrid Indexes Without Network

**User stories covered**

- Story 4: dense tests are deterministic and network-free.
- Story 6: reviewer can compare lexical, dense, and hybrid provenance.
- Story 8: scorecards have a dense backend that works in normal CI.

**Observable behaviors**

- A deterministic dense index can be built without optional dependencies.
- Dense query and hybrid query work through public CLI commands.
- Hybrid results merge duplicate lexical and dense chunks.
- Manifests record deterministic embedding backend evidence without presenting
  it as production retrieval.

**First RED test**

- A deterministic dense fixture corpus cannot be indexed and queried through the
  public retrieval CLI without FastEmbed, Qdrant, network, or model downloads.

### What to build

Add deterministic embedding generation and dense index/query behavior behind a
test/fixture backend. Wire lexical, dense, and hybrid query modes through the
retrieval CLI and shared manifest shapes.

### Acceptance criteria

- [x] Deterministic dense backend is stable across runs.
- [x] Deterministic dense backend requires no network.
- [x] Deterministic dense backend requires no model download.
- [x] Dense index build works with `--dense-backend deterministic`.
- [x] Dense query works with `--mode dense`.
- [x] Hybrid query works with `--mode hybrid`.
- [x] Duplicate lexical/dense results are merged.
- [x] Per-method scores and provenance are visible.
- [x] `retrieval_backend.v2` records deterministic backend evidence and
      `remote_embeddings: false`.
- [x] Docs mark the deterministic dense backend as test/fixture-only.

### Out of scope

- FastEmbed model execution.
- Qdrant persistence.
- Runtime provider-input integration beyond query output.

---

## Phase 4: Hybrid Retrieval Is Policy-Filtered Before Context Assembly

**User stories covered**

- Story 6: context manifests show lexical/dense/both provenance.
- Story 7: denied and sensitive chunks cannot enter accepted context.
- Story 8: scorecards and evals use policy-filtered retrieval evidence.

**Observable behaviors**

- Runtime context assembly can use a built retrieval index.
- Lexical, dense, and hybrid retrieval candidates are filtered by policy before
  accepted manifest items are created.
- Rejected items include rejection reason, policy decision, and sensitivity
  evidence without leaking rejected text.
- Provider input receives only accepted context manifest records.

**First RED test**

- A dense result from a denied or sensitive file appears in accepted context or
  provider input instead of `rejected_items`.

### What to build

Wire retrieval index lookup into the existing context assembly boundary. Keep
retrieval untrusted and let policy, sensitivity classification, redaction, and
provider-input rules decide what can be included.

### Acceptance criteria

- [x] Hybrid retrieval runs through context assembly.
- [x] Context manifests record lexical provenance.
- [x] Context manifests record dense provenance.
- [x] Context manifests record both-provenance for merged duplicates.
- [x] Context manifests record per-method scores.
- [x] Context manifests record backend and index evidence.
- [x] Included and rejected items are both inspectable.
- [x] Rejected items include rejection reasons, sensitivity classes, and policy
      decisions.
- [x] Denied chunks are rejected before context assembly acceptance.
- [x] Sensitive chunks that policy denies are rejected before context assembly
      acceptance.
- [x] Provider input receives only policy-accepted context.
- [x] Lexical fallback remains deterministic and inspectable.

### Out of scope

- Persistent Qdrant local storage.
- Loopback Qdrant server.
- Scorecard CLI output.

---

## Phase 5: Local FastEmbed And Persistent Qdrant Work As Optional Retrieval

**User stories covered**

- Story 2: developer can build persistent local Qdrant indexes.
- Story 3: reviewer can inspect Qdrant-backed manifests.
- Story 10: release reviewer can run the local retrieval golden path.

**Observable behaviors**

- With retrieval extras installed, a user can build a persistent local Qdrant
  index using local FastEmbed embeddings.
- Query and context assembly use the same policy and manifest boundaries as
  lexical and deterministic dense retrieval.
- Missing model/dependency conditions are clear and fall back only according to
  config.

**First RED test**

- `agent-harness retrieval index build --dense-backend qdrant-local` either
  fails despite retrieval extras being installed or lacks reproducible manifest
  evidence for storage path, collection, model, and version.

### What to build

Add the optional `qdrant-local` backend with FastEmbed local embeddings,
persistent local Qdrant storage, lifecycle support, query support, fallback
diagnostics, and integration/smoke coverage.

### Acceptance criteria

- [x] Retrieval extra enables FastEmbed and Qdrant-backed retrieval.
- [x] FastEmbed runs locally.
- [x] Embedding model name is recorded.
- [x] Embedding model version is recorded where available.
- [x] First-run model acquisition behavior is documented.
- [x] Model cache location is documented.
- [x] Qdrant local storage defaults under `.agent-harness/indexes/`.
- [x] Qdrant collection name is recorded.
- [x] Rebuild and delete lifecycle work for local Qdrant indexes.
- [x] Missing dependency diagnostics are clear.
- [x] Lexical fallback works according to config.
- [x] Optional FastEmbed/Qdrant tests skip unless retrieval extras are
      installed.

### Out of scope

- Loopback server backend.
- Cloud or API-key-backed Qdrant.
- Production Qdrant operations.

---

## Phase 6: Loopback Qdrant Server Is Allowed Only As Local Developer Infrastructure

**User stories covered**

- Story 5: unsupported remote retrieval endpoints are rejected.
- Story 9: local developers can test loopback server infrastructure.
- Story 10: reviewers can verify server diagnostics and scope boundaries.

**Observable behaviors**

- `qdrant-server` accepts only `localhost`, `127.0.0.1`, and `::1`.
- Non-loopback endpoints fail before document content can be indexed or queried.
- Unreachable loopback endpoints produce actionable diagnostics.
- Loopback server retrieval uses the same manifest and policy-filtering behavior
  as other retrieval backends.

**First RED test**

- A `qdrant-server` config pointing at a private LAN IP, public IP, cloud URL,
  API-key-backed endpoint, or remote HTTPS endpoint is accepted.

### What to build

Add endpoint validation and optional loopback Qdrant server index/query support.
Keep tests optional unless an explicit environment flag and server are present.

### Acceptance criteria

- [x] `localhost` is accepted.
- [x] `127.0.0.1` is accepted.
- [x] `::1` is accepted.
- [x] Public IP endpoints are rejected.
- [x] Private LAN IP endpoints are rejected.
- [x] Cloud URLs are rejected.
- [x] API-key-backed endpoints are rejected.
- [x] Remote HTTPS endpoints are rejected.
- [x] Unreachable loopback server diagnostics are actionable.
- [x] Backend, endpoint identity, collection, model/version, and fallback
      diagnostics are recorded.
- [x] Same policy and sensitivity filtering applies as every other backend.
- [x] Normal CI skips loopback server tests unless explicitly enabled.
- [x] Docs describe this as local developer infrastructure only.

### Out of scope

- Production server operations.
- Remote Qdrant service support.
- Hosted retrieval credentials.

---

## Phase 7: Retrieval Scorecards Compare Lexical, Dense, And Hybrid Quality

**User stories covered**

- Story 6: reviewers can compare retrieval modes.
- Story 8: maintainers can measure retrieval quality.
- Story 10: release reviewer can inspect generated scorecards.

**Observable behaviors**

- Fixture corpora define queries, expected relevant chunks, and allowed
  sensitivity classes.
- `agent-harness retrieval scorecard` computes Precision@k and Recall@k.
- Scorecards compare lexical, dense, and hybrid modes without remote services.
- Release readiness can verify at least one passing retrieval scorecard.

**First RED test**

- A labeled fixture corpus cannot produce a `retrieval_scorecard.v1` comparing
  lexical, deterministic dense, and hybrid retrieval through the public CLI.

### What to build

Add scorecard fixture format, metric computation, per-query result recording,
backend comparison output, and release-readiness evidence hooks.

### Acceptance criteria

- [x] Fixture corpora define queries.
- [x] Fixture corpora define expected relevant chunks.
- [x] Fixture corpora define allowed sensitivity classes.
- [x] Scorecard computes Precision@k.
- [x] Scorecard computes Recall@k.
- [x] Scorecard compares lexical, dense, and hybrid modes.
- [x] Scorecard records per-query hits.
- [x] Scorecard records per-query misses.
- [x] Scorecard records unexpected results.
- [x] Scorecard output is written as `retrieval_scorecard.v1`.
- [x] Scorecard can run without remote services.
- [x] Scorecard works with deterministic dense backend in normal tests.
- [x] Optional FastEmbed/Qdrant scorecard runs only when retrieval extras are
      installed.
- [x] Release readiness verifies at least one retrieval scorecard exists and
      passes.

### Out of scope

- Large public benchmark datasets.
- Hosted model evaluation.
- Ranking optimization beyond basic V5 comparison.

---

## Phase 8: Retrieval Demo And V5 Golden Path Are Release-Ready

**User stories covered**

- Story 2: developer can run persistent local retrieval.
- Story 3: reviewer can inspect Qdrant-backed manifests.
- Story 7: policy filtering is visible in the demo.
- Story 10: release reviewer can run the V5 golden path.

**Observable behaviors**

- `examples/retrieval_quality/` demonstrates lexical build, dense local build
  when extras are installed, hybrid query, context manifest provenance,
  denied/sensitive rejection, and scorecard comparison.
- The final V5 golden path works from a clean checkout with retrieval extras
  installed.
- Release readiness reports retrieval evidence and rejects default remote
  retrieval settings.

**First RED test**

- The documented V5 golden path cannot run end to end from a clean checkout with
  retrieval extras installed.

### What to build

Add the local retrieval quality demo, generated example artifacts, README links,
release-readiness retrieval checks, and final docs updates. Confirm no default
example enables remote embeddings or cloud Qdrant.

### Acceptance criteria

- [x] `examples/retrieval_quality/README.md` exists.
- [x] `examples/retrieval_quality/config.v2.yaml` uses local-first retrieval.
- [x] `examples/retrieval_quality/policy.v2.yaml` demonstrates policy filtering.
- [x] Demo docs include architecture, coding rules, public notes, and sensitive
      or denied internal notes.
- [x] Demo expected artifacts include retrieval index and scorecard examples.
- [x] Demo scorecard fixture exists.
- [x] Lexical index build is demonstrated.
- [x] Dense local index build is demonstrated when retrieval extra is installed.
- [x] Hybrid query is demonstrated.
- [x] Context manifest shows lexical, dense, and both provenance.
- [x] Denied or sensitive chunks are rejected before context assembly.
- [x] Precision@k and Recall@k scorecard comparison is visible.
- [x] V5 golden path works:

      ```powershell
      uv sync --extra retrieval
      uv run agent-harness retrieval index build --index-id demo-retrieval --paths examples/retrieval_quality/docs --mode hybrid --dense-backend qdrant-local
      uv run agent-harness retrieval query demo-retrieval --query "refactor config loader policy" --mode hybrid --k 5
      uv run agent-harness retrieval scorecard examples/retrieval_quality/scorecard.yaml --index-id demo-retrieval --k 5
      uv run agent-harness release readiness
      ```

- [x] Release readiness includes retrieval checks.
- [x] README links to the retrieval demo.
- [x] Roadmap accurately marks cloud and remote retrieval as future.
- [x] No docs claim production Qdrant server mode.
- [x] No executable default config uses remote embeddings.

### Out of scope

- Tagging v1.2.0.
- Publishing packages.
- Implementing remote retrieval roadmap items.

## Cross-Phase Invariants

- Retrieval results are untrusted evidence.
- No retrieval backend bypasses policy evaluation.
- No retrieval backend bypasses sensitivity classification.
- Denied data never enters accepted context, provider input, run execution,
  evals, scorecards, or demos.
- `remote_embeddings: false` is recorded wherever embedding backend evidence is
  relevant.
- Remote embeddings, hosted embedding providers, cloud Qdrant, API-key-backed
  Qdrant, HTTPS remote Qdrant, and remote vector databases remain denied.
- Base install remains functional with lexical retrieval.
- Optional dependency failures produce actionable diagnostics.
- Normal CI remains deterministic and network-free.
- Tests verify public CLI, runtime, schema, and artifact behavior.
- No subsystem is added unless the current or next slice exercises it through an
  observable behavior.
- Docs keep V5 implemented behavior separate from roadmap behavior.

## TDD Execution Rules

- Choose one observable behavior per slice.
- Write one failing public-interface test first.
- Implement the minimum code needed for green.
- Refactor only after tests are green.
- Do not build horizontal infrastructure unless the current or immediately next
  slice exercises it.
- Do not write all tests upfront.
- Do not implement roadmap features without an observable behavior and an
  acceptance test.

## Final Acceptance

V5 is complete only when the following path works from a clean checkout with
retrieval extras installed:

```powershell
uv sync --extra retrieval

uv run agent-harness retrieval index build `
  --index-id demo-retrieval `
  --paths examples/retrieval_quality/docs `
  --mode hybrid `
  --dense-backend qdrant-local

uv run agent-harness retrieval query demo-retrieval `
  --query "refactor config loader policy" `
  --mode hybrid `
  --k 5

uv run agent-harness retrieval scorecard examples/retrieval_quality/scorecard.yaml `
  --index-id demo-retrieval `
  --k 5

uv run agent-harness release readiness
```

V5 is also complete only when base install lexical retrieval still works,
retrieval docs are accurate, scorecards are generated, Qdrant-backed context
manifests are inspectable, lexical/dense/hybrid comparison is visible,
denied/sensitive chunks are rejected before context assembly, default examples
do not enable remote embeddings, no cloud Qdrant config exists in executable
examples, and all required tests and gates pass.
