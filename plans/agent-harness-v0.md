# Plan: Agent Harness V0 Recovery

> Source PRD: `docs/prd-agent-harness-v0.md`

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: V0 is a Python CLI with `init`, `template
  list/show/apply`, `ingest docs`, `task validate`, `run`, `approve`,
  `inspect run/context/policy`, `eval`, `export sarif`, and `doctor`.
- **Key models**: task, tool, policy, template, eval, approval, context
  manifest, run event, checkpoint, and summary are public boundary models.
- **Repo structure**: use the research skeleton as the target structure, but
  restructure only when a vertical slice requires it.
- **Storage**: each run writes artifacts under `.agent-harness/runs/<run-id>`;
  JSONL events are the audit trail and SQLite stores inspectable metadata.
- **Runtime boundary**: V0 uses a native plan-act-observe loop and a
  deterministic mock model. Framework adapters stay out of V0 implementation.
- **Policy boundary**: policy profiles are permission ceilings. No subsystem
  may bypass policy.
- **Context boundary**: all external data, retrieved content, prompts, model
  output, and tool output are untrusted evidence.
- **Approval model**: risky mutation pauses for review and can execute only
  with a matching approval binding.
- **Retrieval boundary**: deterministic local retrieval is default, fake
  retrieval is for isolated unit tests, and Qdrant/FastEmbed is optional smoke
  path only.
- **Docs boundary**: public docs describe implemented behavior; V1/V2 remain
  roadmap only.

---

## Phase -1: Recovery Foundation

**User stories covered**

- Story 10: maintainers can evaluate regressions from a clear plan.

**Observable behaviors**

- The repository has a V0 PRD.
- The repository has a vertical implementation plan.
- The current spike is classified as salvage, rewrite, or discard.

**First RED test**

- None. This is a recovery gate before implementation resumes.

### What to build

Create the missing product and planning artifacts. Audit the spike without
migrating code or restructuring the repository.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v0.md` exists and defines V0 scope.
- [x] `plans/agent-harness-v0.md` exists and slices work by public behavior.
- [x] `docs/spike-audit.md` exists and classifies spike material.
- [x] No code migration or package restructuring occurs in this phase.
- [x] The first Phase 0 RED test is identified.

### Out of scope

- Code changes.
- Test rewrites.
- Repo restructuring.
- Promoting private research notes into public docs.

---

## Phase 0: Walking Skeleton Dry Run

**User stories covered**

- Story 3: a dry-run task creates inspectable artifacts.
- Story 5: a reviewer can inspect run evidence.

**Observable behaviors**

- A minimal dry-run task creates a run id and run directory.
- The run contains a policy-mediated minimal context manifest.
- The run contains a JSONL event log, checkpoint, summary, and artifact index.
- `inspect run <run-id>` works for that run.

**First RED test**

- `agent-harness run <task> --dry-run` emits required artifacts and
  `agent-harness inspect run <run-id>` returns summary plus event evidence.

### What to build

Build the smallest end-to-end path through config loading, task validation,
policy loading, context manifest creation, run storage, event writing, summary
writing, and run inspection.

### Acceptance criteria

- [x] Dry-run creates exactly one run directory with required artifacts.
- [x] The context manifest records policy decision evidence.
- [x] The event log includes `run_started`, context creation, checkpoint, and
      `run_finished` events.
- [x] `inspect run` reads artifacts rather than recomputing state.
- [x] No file mutation happens in dry-run.

### Out of scope

- Patch approvals.
- Retrieval indexing.
- SQLite richness beyond what inspection needs.
- Full project skeleton.

---

## Phase 1: Project Foundation

**User stories covered**

- Story 1: initialize a local project.
- Story 2: validate task and policy specs.

**Observable behaviors**

- `init` creates expected config, policy, artifact directories, and starter
  docs.
- `template list/show/apply` works for `python-lib`.
- Generated docs contain no unsupported V0 claims.

**First RED test**

- `agent-harness init` in an empty directory creates expected structure, and a
  documentation scanner fails if V0 docs claim behavior not yet implemented.

### What to build

Create only the project foundation needed for initialization, template
application, validation, and honest docs. Introduce the research skeleton
incrementally when these commands need it.

### Acceptance criteria

- [x] `init` is idempotent unless `--force` is supplied.
- [x] `python-lib` template application is policy-mediated.
- [x] `task validate` returns concrete validation errors for invalid specs.
- [x] Public docs separate implemented V0 behavior from roadmap items.
- [x] Project metadata supports local install and test execution.

### Out of scope

- Additional templates.
- Provider integrations.
- Full docs site polish.

---

## Phase 2: Stable Storage And Audit

**User stories covered**

- Story 3: dry-run artifacts are reproducible.
- Story 10: evals and exports consume stable evidence.

**Observable behaviors**

- A fixed-seed run produces stable required artifacts.
- JSONL events, SQLite metadata, checkpoints, and summaries agree.
- Events include correlation ids where a workflow step spans decisions and
  observations.

**First RED test**

- Two fixed-seed dry-runs produce the same required metadata and artifact
  hashes, excluding explicitly time-bound fields.

### What to build

Strengthen run storage only where the dry-run behavior needs it: metadata,
event append semantics, checkpoint hashes, summary consistency, and artifact
hashes.

### Acceptance criteria

- [x] JSONL event count matches summary metadata.
- [x] SQLite run and event rows match artifact files.
- [x] Checkpoint hash includes task, manifest, policy, and prior-event
      evidence.
- [x] Re-running with fixed run id is rejected or handled explicitly.
- [x] Summary artifacts are inspectable without executing the runtime.

### Out of scope

- Remote storage.
- Retention profiles beyond documented placeholders.
- OpenTelemetry.

---

## Phase 3: Policy Blocks Denied Data

**User stories covered**

- Story 4: context evidence is auditable.
- Story 5: denied data cannot enter context or tools.

**Observable behaviors**

- Denied file paths cannot enter context construction.
- Denied file paths cannot execute through tools.
- Policy profiles define ceilings that task specs can only narrow.
- Redaction applies before model-facing context or observations are stored.

**First RED test**

- A task referencing an allowed file and a denied file creates a context
  manifest containing only the allowed file, and a tool call for the denied file
  is denied with policy evidence.

### What to build

Build policy decisions through the public context and tool boundaries. Add only
the rules required by denied data, ceilings, path sandboxing, sensitivity
labels, deny globs, and redaction.

### Acceptance criteria

- [x] Path traversal is rejected.
- [x] Deny globs override read and write roots.
- [x] Task-level allowed tools cannot widen profile tools.
- [x] Secret-like content is redacted in model-facing artifacts.
- [x] Policy decisions are logged for allowed and denied cases.

### Out of scope

- Enterprise DLP.
- External secret scanners.
- Network policy beyond deny-by-default metadata.

---

## Phase 4: Approval-Bound Tool Execution

**User stories covered**

- Story 6: supported tools execute through policy.
- Story 7: patch proposals pause before mutation.
- Story 8: approved patches are hash-bound.

**Observable behaviors**

- `patch_file` produces a diff and approval request without mutation.
- An approved patch applies only if the approval binding still matches.
- Non-mutating tools produce policy-mediated observations.

**First RED test**

- `patch_file` with approval required writes an approval record and generated
  diff, leaves the target unchanged, and returns `pending_approval`.

### What to build

Implement the narrow public tool set through a common executor: `read_file`,
`search_code`, `run_tests`, `patch_file`, and `git_status`. Add approval-bound
mutation only after the pending-approval behavior is green.

### Acceptance criteria

- [x] `patch_file` uses hash-checked full replacement.
- [x] Approval binding includes run id, action id, tool name, arguments hash,
      policy profile, checkpoint hash, and proposed effect hash.
- [x] Stale, tampered, or mismatched approvals fail before mutation.
- [x] `run_tests` accepts only allow-listed argv arrays.
- [x] Tool observations are recorded as run evidence.

### Out of scope

- General shell tool.
- Git commit or branch mutation.
- Multi-file patch batches unless covered by a later behavior test.

---

## Phase 5: Context And Retrieval

**User stories covered**

- Story 4: context has provenance and policy evidence.
- Story 5: denied data is excluded from context.

**Observable behaviors**

- `ingest docs` creates deterministic local retrieval metadata.
- Context manifests are reproducible under fixed seeds.
- Retrieval results carry source, chunk, hash, sensitivity, and policy evidence.
- Denied retrieved content is excluded.

**First RED test**

- A fixed-seed task with ingested docs creates the same context manifest across
  runs, and a denied retrieved document is absent with a logged policy denial.

### What to build

Add docs ingest, chunking, lexical retrieval, fake retrieval for unit tests, and
optional Qdrant/FastEmbed smoke validation behind the retriever boundary.

### Acceptance criteria

- [x] Ingest output is deterministic for the same inputs.
- [x] Context chunks include provenance and content hashes.
- [x] Sensitivity labels appear in manifests.
- [x] Redaction happens before retrieved text enters the manifest.
- [x] Optional retrieval dependencies are not required for normal local runs.

### Out of scope

- Server-backed vector retrieval as required behavior.
- Benchmark-scale retrieval.
- Prompt assembly beyond manifest construction.

---

## Phase 6: Runtime, Mock Model, And Resume

**User stories covered**

- Story 8: approval resume is bound and safe.
- Story 9: mock model behavior depends on real inputs.

**Observable behaviors**

- The runtime performs a plan-act-observe loop.
- The mock model consumes task specs, context, and observations.
- Approval pause and resume work from a checkpoint.
- Changing relevant context or observations changes proposed behavior.

**First RED test**

- Two runs with the same task id but different context or observations produce
  different next actions, and approval resume applies only the approved,
  hash-bound patch.

### What to build

Connect model planning, tool observations, checkpointed pause, approval update,
and resume into one testable workflow. Keep model/provider interfaces small and
provider-neutral.

### Acceptance criteria

- [x] Task id alone is insufficient to drive mock-model behavior.
- [x] Runtime records model actions and observations as evidence.
- [x] Paused runs can be inspected before approval.
- [x] Approved runs update summary and audit evidence after resume.
- [x] Denied approvals leave files unchanged and remain inspectable.

### Out of scope

- Network model clients.
- Streaming output.
- Multi-agent orchestration.

---

## Phase 7: Evals, Export, And CI

**User stories covered**

- Story 10: maintainers can catch regressions and export evidence.

**Observable behaviors**

- `eval` runs local scenarios for success, denial, prompt injection, approval
  flow, and reproducible replay.
- Evals fail hard on policy bypass.
- Exports emit JSON, Markdown, and SARIF artifacts from run evidence.
- CI runs the V0 acceptance checks.

**First RED test**

- An adversarial eval that attempts a policy bypass fails and emits a scorecard
  artifact explaining the failed invariant.

### What to build

Build eval scenarios only around implemented public behavior. Add export
formats and CI after they have real evidence to consume.

### Acceptance criteria

- [x] Eval scorecards include pass/fail status and artifact links.
- [x] Policy bypass attempts are hard failures.
- [x] SARIF output reflects policy decisions from run events.
- [x] Markdown and JSON exports match the run summary and event log.
- [x] CI runs unit, integration, e2e, adversarial, lint, and type checks as
      those checks become available.

### Out of scope

- SWE-bench or Terminal-Bench adapters.
- Hosted dashboards.
- Release automation beyond basic CI.

## Cross-Phase Invariants

- No subsystem bypasses policy.
- Policy profiles define the permission ceiling.
- External data, retrieval, prompts, model output, and tool output are
  untrusted evidence.
- Context construction passes through policy before runtime or model use.
- No dead architecture is implemented without tested behavior.
- Tests target public behavior, not internals.
- Docs match implemented behavior and avoid overclaiming.
- Mock model behavior depends on real task specs, context, and observations.
- Spike code is reused only after behavior-test coverage.
- V1/V2 remain roadmap only.
