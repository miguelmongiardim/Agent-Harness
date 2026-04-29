# Plan: Agent Harness V10 Schema Boundary Refactor

> Source PRD: [docs/prd-agent-harness-v10.md](../docs/prd-agent-harness-v10.md)

V10 targets `v1.6.1` as a maintenance architecture track. This plan is
intentionally sliced around observable behavior and import-boundary enforcement.
Implementation should proceed through TDD, one behavior at a time.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: remove `agent_harness.schemas` as an import surface.
  New imports use boundary-owned modules such as
  `agent_harness.templates.schema`.
- **Key models**: preserve all existing model fields, defaults, validators,
  strict Pydantic behavior, and serialized output while moving definitions to
  owner modules.
- **Schema**: no JSON schema version changes; this is a Python ownership
  refactor, not a data migration.
- **Storage**: persisted run evidence, approvals, checkpoints, summaries,
  workspace metadata, and artifact layouts remain unchanged.
- **Runtime boundary**: runtime coordinates contracts from owning packages
  without becoming the owner of every schema.
- **Policy boundary**: policy remains the owner of policy contracts,
  sensitivity, and policy decision records.
- **Approval model**: approval records and bindings retain current behavior and
  exact-effect protections.
- **Audit model**: existing audit artifacts remain byte-shape compatible except
  for incidental formatting only where tests already allow it.
- **External service boundary**: no new services, providers, network behavior,
  MCP capabilities, or optional dependencies.

---

## Phase 0: Ownership Guard And Planning Baseline

**User stories covered**

- Story 2: contributor has an obvious place to add a contract.
- Story 6: test maintainer can prevent `agent_harness.schemas` from returning.
- Story 7: config maintainer has a safe path for package conversion.

**Observable behaviors**

- V10 PRD and vertical plan exist.
- A future implementation has a failing import-boundary test while
  `agent_harness.schemas` exists or source imports it.
- The guard describes allowed owner-module imports without requiring the schema
  moves to be complete.

**First RED test**

- Add a test that scans `src/agent_harness` and `tests` and fails if
  `src/agent_harness/schemas.py` exists or if any Python source imports
  `agent_harness.schemas`.

### What to build

Add only the guard test and any minimal test helper needed to produce a clear
failure. Do not move schemas in this phase.

### Acceptance criteria

- [x] The V10 PRD exists and follows the PRD template.
- [x] The V10 plan exists and uses vertical slices.
- [x] The import-boundary test fails against the current root schema module.
- [x] No production code is changed in the planning-only branch.

### Out of scope

- Moving schema models.
- Updating imports.
- Changing CLI, artifact, or runtime behavior.

---

## Phase 1: Template Boundary Proves The Pattern

**User stories covered**

- Story 1: maintainer sees schema ownership beside behavior.
- Story 4: template maintainer has a real `templates.schema` boundary.
- Story 5: release maintainer gets unchanged template behavior.

**Observable behaviors**

- Template catalog, show, validation, dry-run planning, and apply evidence still
  work.
- Template code imports template contracts from `agent_harness.templates.schema`.
- `agent_harness.templates.schema` defines owned template models directly.

**First RED test**

- Update template schema/import tests so they expect template contracts to be
  owned by `agent_harness.templates.schema` and reject a re-export-only facade.

### What to build

Move template-owned models into `templates/schema.py`, update template package
imports, and keep generated template evidence identical.

### Acceptance criteria

- [x] Template catalog tests pass.
- [x] Template validation and apply planning tests pass.
- [x] `TemplateSpec`, `TemplateDetail`, and template application records are
      imported from `agent_harness.templates.schema`.
- [x] No template JSON manifest schema version changes.

### Out of scope

- Moving non-template models.
- Changing template rendering or apply semantics.

---

## Phase 2: Independent Boundary Schemas

**User stories covered**

- Story 1: maintainer sees ownership in import paths.
- Story 3: reviewer can inspect dependency direction.
- Story 5: release maintainer sees unchanged behavior for independent
  boundaries.

**Observable behaviors**

- Skills, operator, eval, benchmark, security, runtimes, and MCP schema
  contracts validate through their owner modules.
- Existing CLI and inspection workflows for those boundaries behave unchanged.
- Boundary modules define owned models instead of importing them from a root
  schema module.

**First RED test**

- Add or update one focused import/validation test for a low-coupling boundary,
  starting with skills or operator, that imports contracts from the owner module.

### What to build

Move low-coupling models in small batches: skills, operator API responses,
evals, benchmarks, security reports, runtime adapter records, and MCP response
contracts where applicable.

### Acceptance criteria

- [x] Skill validation, resolution, and manifest tests pass.
- [x] Operator API tests pass.
- [x] Eval and benchmark tests pass.
- [x] Security scanner/export behavior remains unchanged.
- [x] Runtime adapter record behavior remains unchanged.
- [x] No owner module is only a schema re-export facade.

### Out of scope

- Moving the cross-cutting runtime, policy, tool, context, model, storage,
  config, or task contracts.

---

## Phase 3: Core Cross-Boundary Contracts

**User stories covered**

- Story 1: maintainers can locate core contracts by owner.
- Story 3: reviewers can catch dependency inversions.
- Story 5: release maintainers can verify no public behavior drift.
- Story 7: config maintainers can separate config schemas from config loading.

**Observable behaviors**

- Runtime, migration, policy, tool execution, provider gateway, context
  assembly, retrieval, storage, config loading, and task validation continue to
  work.
- `agent_harness.config` remains importable for existing loader functions.
- Cross-boundary records are owned by the package that persists or validates
  them.

**First RED test**

- Add a focused config package test proving `from agent_harness.config import
  load_config` still works while `HarnessConfig` is imported from
  `agent_harness.config.schema`.

### What to build

Move the cross-cutting contracts while preserving dependency direction:
policy owns policy contracts, tools own tool calls and git commit plans, model
owns provider contracts, context owns retrieval and context manifests, storage
owns run evidence and workspace metadata, tasks owns task specs, and config owns
harness config while importing provider config from model.

### Acceptance criteria

- [x] Config loading and schema-evidence tests pass.
- [x] Runtime unit, integration, and adversarial tests pass for the moved
      contracts.
- [x] Migration tests pass without serialized schema-version drift.
- [x] Provider gateway, provider input, retrieval, storage, policy, and tool
      tests pass.
- [x] No foundational package imports a higher-level package solely for schema
      definitions.

### Out of scope

- Altering field names, defaults, validation semantics, or artifact layouts.
- Introducing a compatibility import aggregator.

---

## Phase 4: Delete Root Schema Surface

**User stories covered**

- Story 2: contributors cannot add contracts to a root dumping ground.
- Story 6: test maintainers can enforce the new boundary.
- Story 5: release maintainers can validate unchanged product behavior.

**Observable behaviors**

- `agent_harness.schemas` no longer exists.
- Source and tests contain no imports from `agent_harness.schemas`.
- Full local validation passes through owner-module imports.

**First RED test**

- Run the Phase 0 import-boundary test after all imports have been updated; it
  should pass only when the root schema module is gone.

### What to build

Remove the root schema module, update any remaining imports, and adjust docs or
comments that still describe a centralized schema module.

### Acceptance criteria

- [x] Import-boundary guard passes.
- [x] `rg "agent_harness\\.schemas" src tests docs plans README.md` finds no
      stale implementation or docs references except historical notes if
      explicitly allowed by the test.
- [x] Focused unit, integration, adversarial, and e2e checks pass.
- [x] `agent-harness docs check` passes if docs were changed.

### Out of scope

- Adding deprecation shims.
- Changing public JSON schemas or CLI behavior.
- Publishing or tagging `v1.6.1`.

## Cross-Phase Invariants

- No phase changes serialized artifact schema versions.
- No phase changes CLI behavior or command output shapes.
- No phase implements a compatibility aggregator for `agent_harness.schemas`.
- Boundary schema modules define owned models; they are not re-export-only
  facades.
- Imports preserve package dependency direction.
- Tests verify behavior through public interfaces, owner-module imports, and
  persisted artifacts.
- Refactoring happens only after the relevant behavior is protected by tests.
- Roadmap or release docs are updated only when needed to keep public claims
  accurate.
