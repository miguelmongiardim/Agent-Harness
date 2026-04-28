# Plan: Agent Harness V7 Template Pack System

> Source PRD: [docs/prd-agent-harness-v7.md](../docs/prd-agent-harness-v7.md)

V7 targets `v1.4.0`. No implementation phases have been completed yet. Release
tagging and package publishing remain outside this implementation plan.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: extend `agent-harness template list/show/validate/apply`;
  add `template pack validate <path>`; prefer `--target` while preserving
  `--destination` as an alias.
- **Manifest format**: use `template.v2.toml` with `tomllib`; do not add PyYAML
  solely for template manifests.
- **Compatibility model**: keep legacy `template.v1` and bundled JSON
  readability; use simple min/max Agent Harness version fields for V7 pack
  compatibility.
- **Key models**: add or extend public template detail, validation, apply-plan,
  and `template_application.v1` evidence models without changing existing
  template IDs.
- **Template boundary**: keep manifest loading, source discovery, validation,
  deterministic rendering, write planning, and evidence construction inside
  `agent_harness.templates`.
- **Runtime boundary**: keep approval-bound apply orchestration in the runtime;
  do not move general run orchestration into the template package.
- **Policy boundary**: policy remains the gate for template capabilities,
  filesystem writes, non-empty target mutation, and overwrite approval.
- **Storage boundary**: actual applies persist `template_application.v1` under
  `.agent-harness/template_applications/` and update workspace metadata; dry-run
  and preview do not persist evidence.
- **Rendering boundary**: support deterministic `{{ param_name }}` substitution
  only; no hooks, scripts, environment reads, remote reads, conditionals, loops,
  filters, includes, or code execution.
- **Local source boundary**: discover local packs only from explicit
  `config.v2` `templates.local_dirs`; never scan arbitrary directories.
- **Release boundary**: release readiness is the V7 control surface for bundled
  pack validation, dry-run, clean apply, generated schema checks, docs, and
  remote catalog default rejection.

---

## Phase 0: V7 Scope Is Documented And Guarded

**User stories covered**

- Story 10: release reviewer can verify V7 from a clean checkout.
- Story 12: documentation reviewer can distinguish implemented local behavior
  from roadmap behavior.

**Observable behaviors**

- V7 PRD and plan exist.
- Template-pack docs describe local-first V7 behavior.
- Docs checks reject implemented-scope claims for remote catalogs,
  marketplaces, signing, organization catalogs, cloud registries, hooks,
  scripts, enterprise governance, and conditional file inclusion.

**First RED test**

- `agent-harness docs check` passes while a doc says Agent Harness provides a
  remote template catalog as implemented behavior.

### What to build

Add the durable V7 docs and docs-check guarded phrases needed to lock scope
before implementation starts. Update README, roadmap, architecture, and release
readiness docs only enough to point at the planned V7 local template-pack
boundary and keep roadmap-only claims out of implemented sections.

### Acceptance criteria

- [x] `docs/prd-agent-harness-v7.md` exists and follows the PRD template.
- [x] `plans/agent-harness-v7.md` exists and uses vertical slices.
- [x] `docs/template-pack-system.md` describes V7 local template packs.
- [x] README and roadmap describe V7 as local-first and keep remote template
      features future-only.
- [x] Architecture docs identify `agent_harness.templates` as the pack-system
      boundary.
- [x] Release-readiness docs name the V7 template-pack gates.
- [x] Docs check rejects unsupported template-pack claims outside roadmap
      sections.
- [x] Docs check passes after docs are corrected.

### Out of scope

- Manifest loading.
- CLI behavior changes.
- Template application changes.

---

## Phase 1: Reviewer Can Discover And Inspect A Bundled Pack

**User stories covered**

- Story 1: developer can list template packs.
- Story 2: developer can inspect template metadata.
- Story 11: existing IDs and legacy templates remain stable.

**Observable behaviors**

- `template list` includes a `python-lib` bundled pack with source and
  compatibility metadata.
- `template show python-lib` displays pack source, generated files, parameters,
  generated schema versions, capabilities, and demo commands.
- Existing legacy bundled JSON templates remain readable while migration starts.

**First RED test**

- `agent-harness template show python-lib` cannot display pack source, included
  generated files, parameters, generated schema versions, capabilities, and demo
  metadata from a `template.v2.toml` bundled pack.

### What to build

Introduce the minimal pack-source and manifest-reading path needed for one
bundled `python-lib` pack. Keep the existing registry and JSON loader usable so
`cli-tool` and `fastapi-service` do not break during the first migration slice.
Extend list/show output through public models instead of adding a parallel CLI
format.

### Acceptance criteria

- [x] A packaged `python-lib` pack with `template.v2.toml` is discoverable.
- [x] Legacy bundled JSON templates remain listed and showable.
- [x] `template list` reports template ID, version, source type, and
      compatibility.
- [x] `template show python-lib` reports source, files, params, schemas,
      capabilities, and demo metadata.
- [x] Duplicate template IDs fail clearly during discovery.
- [x] Existing `python-lib`, `cli-tool`, and `fastapi-service` IDs remain
      stable.

### Out of scope

- Local user template directories.
- Full validation safety checks.
- Dry-run, preview, or apply behavior changes.

---

## Phase 2: Invalid Packs Fail Validation Before Use

**User stories covered**

- Story 3: template author can validate a local pack directory.
- Story 8: security reviewer can reject unsafe packs before rendering or apply.

**Observable behaviors**

- `template validate python-lib` uses the V7 validator.
- `template pack validate <path>` validates a local pack directory without
  installing it.
- Unsafe packs fail with actionable diagnostics.

**First RED test**

- A local pack containing `../` output, an absolute path, a remote URL source,
  an undeclared placeholder, and a credential-like literal validates
  successfully.

### What to build

Create the shared validator used by both registry-selected templates and direct
pack paths. Validate manifest fields, compatibility, included files, text
content, placeholder declarations, generated schema consistency, local-only
sources, hook/script absence, path safety, and high-risk content markers before
the pack can be used by planning or apply.

### Acceptance criteria

- [x] `template validate <id>` and `template pack validate <path>` use the same
      validator core.
- [x] Required manifest fields, template ID format, version format, and simple
      min/max compatibility validate.
- [x] Included files must exist and be UTF-8 text.
- [x] Traversal, absolute paths, and drive-prefixed paths are rejected.
- [x] Symlink escapes and parent symlink traversal are rejected.
- [x] Remote source declarations are rejected.
- [x] Hook and script declarations are rejected.
- [x] Unsupported placeholders and undeclared placeholders are rejected.
- [x] Secret-like values, generated citation markers, and private uploaded-file
      references are rejected or reported according to the V7 policy decision.
- [x] Hidden or unlisted generated files are denied.
- [x] Generated config, task, policy, and eval examples validate where present.
- [x] Diagnostics are actionable and machine-readable.

### Out of scope

- Applying templates.
- Local source discovery from config.
- Parameter substitution at apply time beyond validation fixtures.

---

## Phase 3: Reviewer Can Dry-Run And Preview A Pack Without Mutation

**User stories covered**

- Story 4: reviewer can dry-run planned changes safely.
- Story 5: reviewer can preview safe diffs safely.
- Story 8: path and symlink safety apply before diff generation.

**Observable behaviors**

- `template apply python-lib --target <path> --dry-run` emits an apply plan and
  evidence-shaped output without mutating files.
- `template apply python-lib --target <path> --preview-diff` emits safe relative
  diffs without mutating files.
- Both modes share the same planning engine that actual apply will later use.

**First RED test**

- `--dry-run` or `--preview-diff` creates target files, run artifacts,
  application evidence, or workspace metadata.

### What to build

Add template rendering and write planning for validated packs without executing
writes. Include planned creates, skips, conflicts, generated schemas,
capabilities, warnings, policy implications, generated files, and apply plan
hash. Preview diffs must use safe relative paths and redact environment-like or
secret-like content.

### Acceptance criteria

- [x] `--target` works and `--destination` remains an alias.
- [x] Repeated `--param key=value` values are accepted by the CLI.
- [x] Dry-run reports planned creates, skips, conflicts, schema versions,
      capabilities, warnings, policy implications, generated files, and plan
      hash.
- [x] Preview diff reports safe relative diffs.
- [x] Dry-run and preview do not write target files.
- [x] Dry-run and preview do not persist run artifacts.
- [x] Dry-run and preview do not persist template application evidence.
- [x] Dry-run and preview do not mutate workspace metadata.
- [x] Traversal and symlink escapes are denied before diff output.
- [x] Hidden or unlisted generated files are denied.
- [x] Diff output redacts environment-like and secret-like values.

### Out of scope

- Persisting `template_application.v1`.
- Non-empty target approval execution.
- Local directory discovery.

---

## Phase 4: Clean Apply Emits Evidence And Validates Generated Examples

**User stories covered**

- Story 6: developer can apply to a clean empty target without approval.
- Story 9: maintainer can inspect template application evidence.
- Story 10: release reviewer can rely on generated schema validation.

**Observable behaviors**

- `template apply python-lib --target <clean-path>` writes only declared files
  inside the target.
- The apply persists `template_application.v1` and updates workspace metadata.
- Generated config, task, policy, and eval examples validate after apply.

**First RED test**

- Clean apply succeeds without persisted evidence or writes outside the target.

### What to build

Execute the planned writes from Phase 3 for clean empty targets. Use two-pass
planning before writing, verify target containment and symlink safety, write
declared files only, update workspace metadata, validate generated examples,
and rollback files created by the operation when a write failure can be safely
rolled back.

### Acceptance criteria

- [ ] Clean empty-target apply succeeds without approval.
- [ ] Apply validates the pack and parameters before writing.
- [ ] Apply writes only declared files.
- [ ] All writes stay inside the target.
- [ ] Symlink escapes and parent symlink traversal are denied.
- [ ] Generated config, task, policy, and eval examples validate.
- [ ] `template_application.v1` is persisted under
      `.agent-harness/template_applications/`.
- [ ] Workspace metadata records the template ID, version, target, and evidence.
- [ ] Evidence includes parameters, planned files, created files, operation
      types, rendered hashes, plan hash, diagnostics, policy profile, and
      status.
- [ ] Failed writes rollback files created by the operation where safe.
- [ ] Failure evidence does not claim success.

### Out of scope

- Local template directory discovery.
- Non-empty target apply.
- Migrating all bundled templates.

---

## Phase 5: Local Packs, Parameters, And Non-Empty Safety Work Together

**User stories covered**

- Story 3: template author can validate and use local packs.
- Story 7: security reviewer gets approval-bound non-empty mutation.
- Story 8: malicious parameters cannot escape the target.

**Observable behaviors**

- Configured local template directories appear in template discovery.
- Declared parameters render deterministically in file text and target paths.
- Non-empty target mutation and overwrite planning cannot write without
  approval.

**First RED test**

- An invalid local pack is silently usable, a collision overwrites by default,
  or a malicious `path_fragment` parameter escapes the target.

### What to build

Extend `config.v2` with `templates.local_dirs`, load only those directories,
surface invalid local packs as diagnostics, and implement deterministic
parameter validation and substitution. Reuse the apply-plan hash and approval
binding for non-empty targets and `--force` overwrite planning.

### Acceptance criteria

- [ ] `templates.local_dirs` is readable from `config.v2`.
- [ ] Existing `template_catalog: bundled` remains readable.
- [ ] Local packs in configured directories are discovered.
- [ ] Invalid local packs appear as diagnostics and are not usable.
- [ ] Duplicate IDs across bundled, legacy, and local sources fail clearly.
- [ ] Required params must be provided or have defaults.
- [ ] Undeclared CLI params fail clearly.
- [ ] Choice params accept only declared values.
- [ ] Boolean params render deterministically.
- [ ] `path_fragment` params cannot traverse, be absolute, contain drive
      prefixes, or escape the target.
- [ ] Direct collisions stop by default.
- [ ] `--force` can create an overwrite plan but does not write without
      approval.
- [ ] Non-empty target mutation requires approval-bound apply planning.
- [ ] Approval binding includes template ID, version, target, planned files,
      operation types, rendered hashes, plan hash, policy profile, and
      checkpoint hash where applicable.

### Out of scope

- Remote source discovery.
- Conditional file inclusion.
- Template create/export commands.

---

## Phase 6: All Bundled Packs Prove Real Workflow Scaffolding

**User stories covered**

- Story 1: developer can choose from the required bundled packs.
- Story 2: developer can inspect workflow-specific generated files.
- Story 10: release reviewer can validate every bundled pack.

**Observable behaviors**

- `python-lib`, `cli-tool`, `fastapi-service`, `provider-audit`, and
  `retrieval-quality` are all bundled V7 packs.
- Each bundled pack validates, dry-runs, and clean-applies.
- Each generated scaffold includes schema-valid Agent Harness workflow files.

**First RED test**

- `template validate --all` passes while one required bundled pack is missing
  docs, generated schema-valid examples, or a runnable validation/demo command.

### What to build

Migrate and expand the bundled templates into pack directories. Keep the Python
trio IDs stable, add `provider-audit` and `retrieval-quality`, and ensure each
pack generates enough Agent Harness workflow surface to prove config, policy,
task, eval, docs, and demo metadata behavior without remote catalogs or hooks.

### Acceptance criteria

- [ ] Required bundled packs are `python-lib`, `cli-tool`, `fastapi-service`,
      `provider-audit`, and `retrieval-quality`.
- [ ] Every bundled pack has `template.v2.toml`.
- [ ] Every bundled pack has README or docs fragment content.
- [ ] Every bundled pack generates config, policy, task, and `eval.v1`
      examples.
- [ ] Every bundled pack has demo metadata.
- [ ] Every bundled pack has at least one runnable validation or demo command
      where practical.
- [ ] Every bundled pack validates.
- [ ] Every bundled pack dry-runs.
- [ ] Every bundled pack clean-applies.
- [ ] Generated examples validate after apply.
- [ ] No bundled pack declares remote catalogs, hooks, scripts, signing,
      marketplace behavior, or cloud registry defaults.

### Out of scope

- Remote template pack distribution.
- Organization-wide registries.
- Enterprise governance templates beyond local examples.

---

## Phase 7: V7 Golden Path And Release Readiness Close The Loop

**User stories covered**

- Story 10: release reviewer can accept V7 from a clean checkout.
- Story 12: docs remain aligned with implemented behavior.

**Observable behaviors**

- `examples/template_pack_system/` demonstrates the V7 golden path.
- `agent-harness release readiness` fails when template-pack evidence is
  missing or unsafe.
- The final V7 golden path works from a clean checkout.

**First RED test**

- `agent-harness release readiness` passes when a bundled pack lacks validation,
  dry-run evidence, clean-apply evidence, docs, generated schema checks, or
  template application evidence.

### What to build

Add the V7 example walkthrough and extend release readiness to execute or
verify the complete template-pack evidence set. Update CI release-evidence
commands only where needed so required V7 checks run in the standard release
path.

### Acceptance criteria

- [ ] `examples/template_pack_system/` exists and documents the V7 golden path.
- [ ] Release readiness validates all bundled packs.
- [ ] Release readiness dry-runs all bundled packs.
- [ ] Release readiness clean-applies all bundled packs to temporary targets.
- [ ] Release readiness validates generated config, task, policy, and eval
      examples.
- [ ] Release readiness confirms template application evidence exists for
      clean applies.
- [ ] Release readiness confirms template docs exist.
- [ ] Release readiness rejects remote catalog defaults.
- [ ] Docs check passes with V7 implemented and roadmap boundaries intact.
- [ ] The final acceptance path works:
      `template list`, `template show python-lib`, `template validate
      python-lib`, dry-run apply, preview-diff apply, clean apply, and
      `release readiness`.

### Out of scope

- Release tagging.
- Package publishing.
- Remote template distribution.

## Cross-Phase Invariants

- Existing public template IDs remain stable.
- Legacy template JSON remains readable unless a compatibility plan explicitly
  changes it.
- Template contents and local metadata are untrusted until validation succeeds.
- No template code path writes outside the selected target.
- No template code path follows symlinks outside the target or project root.
- Dry-run and preview modes never mutate target files, run artifacts,
  application evidence, or workspace metadata.
- Clean empty-target scaffolding does not require approval.
- Non-empty target mutation and overwrites require approval-bound planning.
- Approval bindings include the rendered effect, not just the command request.
- Rendering is deterministic text substitution only.
- No hooks, scripts, environment reads, shell expansion, remote reads, or
  conditional file inclusion enter V7.
- Release readiness remains the evidence control surface for V7 acceptance.
- Tests verify behavior through CLI commands, public models, persisted
  artifacts, and release reports rather than private helper details.
