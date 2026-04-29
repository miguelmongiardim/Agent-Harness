# PRD: Agent Harness V10 Schema Boundary Refactor

V10 targets `v1.6.1` as a maintenance architecture track after the V9 MCP
Boundary release.

## Problem Statement

Agent Harness has strong package boundaries for runtime, policy, context,
tools, templates, skills, storage, provider adapters, benchmarks, evals,
operator APIs, release checks, and MCP evidence. Its schema ownership does not
yet match those boundaries.

Most Pydantic contracts currently live in the root `agent_harness.schemas`
module. That module has become a monolithic dumping ground for unrelated
contracts. It also creates awkward partial boundaries: for example,
`agent_harness.templates.schema` exists, but only re-exports template models
from the root module instead of owning them.

This hurts maintainers and reviewers because schema ownership is unclear,
imports do not communicate dependency direction, package boundaries are easier
to bypass, and future changes to one boundary require editing a large shared
module. It also makes tests less precise: schema behavior is validated through
a global module rather than the public contract owned by the package under
change.

Without this refactor, new schema contracts are likely to continue accumulating
in the root module, increasing coupling and making future boundary work more
expensive.

The affected actors are:

- maintainers who need clear ownership for public contracts
- contributors who need obvious import paths for new schema models
- reviewers who need dependency direction to be visible in code
- release maintainers who need assurance that artifact and CLI behavior remain
  stable while internal imports change

## Solution

V10 moves schema model definitions into boundary-owned `schema.py` modules and
removes the root `agent_harness.schemas` import surface.

The intended developer workflow becomes:

1. Find the package that owns the behavior or artifact.
2. Import its contracts from that package's `schema.py` module.
3. Add new models beside the owning boundary rather than to a root schema
   module.
4. Validate behavior through public CLI, runtime, artifact, and package-boundary
   tests.

The solution introduces a tiny neutral schema foundation at
`agent_harness.schema_base` for `StrictModel` and only genuinely shared schema
helpers. Domain models and domain literals stay with their owning boundary.

The solution deliberately avoids a compatibility aggregator. In this project
stage, breaking `from agent_harness.schemas import ...` is acceptable. V10 must
not change JSON schema versions, serialized artifact shapes, CLI command
behavior, policy behavior, provider behavior, approval behavior, or release
readiness semantics.

## User Stories

1. As a maintainer, I want schema models to live beside the boundary that owns
   their behavior, so that ownership is visible in import paths.
2. As a contributor, I want an obvious place to add a new contract, so that I do
   not extend a root dumping-ground module.
3. As a reviewer, I want imports to expose dependency direction, so that I can
   catch boundary inversions during review.
4. As a template maintainer, I want `agent_harness.templates.schema` to define
   template contracts directly, so that it is a real package boundary rather
   than a re-export facade.
5. As a release maintainer, I want existing CLI behavior and persisted artifact
   shapes to remain unchanged, so that the refactor is architectural rather than
   a product-surface change.
6. As a test maintainer, I want a guard against recreating
   `agent_harness.schemas`, so that schema ownership stays enforceable after
   the refactor.
7. As a config maintainer, I want `agent_harness.config` to become a package
   without breaking existing config-loader imports, so that config schemas and
   config behavior can be separated cleanly.

## Behavioral Requirements

1. The source tree no longer contains an `agent_harness.schemas` module after
   the implementation is complete.
2. Source and tests import schema models from boundary-owned modules such as
   `agent_harness.templates.schema`, `agent_harness.policy.schema`, and
   `agent_harness.tools.schema`.
3. `agent_harness.templates.schema` defines the template models it owns instead
   of re-exporting them from another schema module.
4. `agent_harness.config` remains importable for existing loader functions such
   as `load_config`, even after config becomes a package.
5. Existing public JSON schema versions remain unchanged for config, task,
   policy, template, context, provider, skill, eval, benchmark, operator, MCP,
   run, approval, checkpoint, and workspace artifacts.
6. Existing CLI workflows continue to validate, run, inspect, migrate, apply
   templates, resolve skills, run retrieval paths, inspect operator evidence,
   and inspect MCP resources without behavior changes.
7. A test fails if `agent_harness.schemas` is reintroduced or if source code
   imports it.
8. Boundary-owned schema modules do not become re-export-only facades.
9. Cross-boundary schema imports preserve dependency direction; foundational
   packages must not import higher-level packages just to type a persisted
   record.

## Implementation Decisions

- Add `agent_harness.schema_base` as the neutral home for `StrictModel` and only
  genuinely shared schema helpers.
- Delete `agent_harness.schemas`; do not replace it with a compatibility
  aggregator.
- Convert `agent_harness.config` from a module into a package. Move config
  loading behavior into the package and preserve existing package-level loader
  imports through `config/__init__.py`.
- Add or complete boundary-owned schema modules for config, tasks, policy,
  tools, context, model, storage, templates, skills, evals, benchmarks,
  operator, security, runtimes, and MCP where applicable.
- Keep domain literals with their owner:
  - policy owns sensitivity and policy action literals
  - tools own tool names and tool call contracts
  - model owns provider transport, trust-zone, provider mode, and provider
    envelope literals
  - context owns retrieval method literals and context manifest contracts
  - storage owns run status and persisted run evidence contracts
  - security owns security severity and scanner action literals
- `ProviderProfileConfig` belongs to the model/provider boundary; config models
  may depend on it but should not own it.
- `WorkspaceMetadata` and its persisted records belong to storage, even when
  their fields mention templates or skills.
- `RuntimeAdapterRecord` and runtime adapter literals belong to the runtimes
  boundary.
- Preserve all existing Pydantic field names, defaults, validators, strictness,
  and serialized output unless a focused test proves a required correction.
- Treat this as an import and ownership refactor, not a schema-version migration.

## Testing Decisions

- The first implementation test should be an import-boundary guard that fails
  while `agent_harness.schemas` exists or while source imports it.
- Schema validation tests should move to owner modules and continue checking
  externally observable validation behavior, not private implementation shape.
- Integration tests should prove no behavior change for:
  - config loading and schema evidence
  - task validation and run execution
  - policy loading and enforcement
  - template catalog, validation, planning, and apply evidence
  - skill validation, resolution, and manifest evidence
  - provider gateway envelopes and provider input manifests
  - context manifests, retrieval indexes, and retrieval scorecards
  - storage run summaries, approvals, checkpoints, and workspace metadata
  - eval and benchmark result contracts
  - operator and MCP inspection surfaces
- Docs checks are required only if implementation docs or release docs are
  updated during the refactor.
- Tests should verify public behavior through CLI, package boundary imports, and
  persisted artifacts. They should not assert fragile private file-move details
  beyond the explicit `agent_harness.schemas` deletion guard.

## Out of Scope

- Implementing the schema refactor in the planning branch.
- Changing JSON schema versions.
- Changing CLI command names, arguments, output shapes, or exit behavior.
- Changing persisted artifact shapes or run directory layout.
- Changing policy, approval, provider, retrieval, template, skill, operator, or
  MCP behavior.
- Keeping a compatibility aggregator at `agent_harness.schemas`.
- Adding generated JSON Schema files or OpenAPI schema generation.
- Adding new product capabilities.
- Reworking release readiness beyond checks needed to prove the refactor.

## Further Notes

This PRD assumes `agent_harness.schemas` is not a supported public Python API for
the current release target. If release review later treats that import path as a
public compatibility surface, the implementation should either move to a minor
release or introduce an explicit deprecation phase instead of deleting the
module in `v1.6.1`.

The highest implementation risks are import cycles, misplaced ownership for
cross-boundary records, and accidental serialized artifact drift. The plan
should therefore start with boundary guards and one low-risk vertical slice
before moving cross-cutting contracts.
