# PRD: Agent Harness V7 Template Pack System

## Problem Statement

Agent Harness currently has a local bundled template catalog, but template
behavior is still closer to packaged JSON scaffolding than to a reusable
template-pack system. The existing `python-lib`, `cli-tool`, and
`fastapi-service` templates can be listed, shown, validated, and applied, but
they do not yet provide a first-class way to bootstrap complete Agent Harness
workflow profiles into new repositories.

Without V7, each new repository still needs too much hand wiring for
configuration, policy, task specs, eval specs, docs, contributor instructions,
approval expectations, and release-readiness evidence. That weakens the core
Agent Harness thesis: controlled agent workflows should be repeatable across
repositories through explicit, inspectable, policy-aware local artifacts.

The affected users are maintainers, local developers, template authors, release
reviewers, and security reviewers who need to trust that a template pack can be
validated, previewed, applied, and audited without hidden mutation or remote
catalog behavior.

## Solution

V7 targets `v1.4.0` and introduces the Template Pack System: a local-first
template-pack capability for bootstrapping controlled Agent Harness workflows
into new or existing repositories. It preserves the current public template IDs,
keeps legacy `template.v1` and bundled JSON readability where supported, and
adds versioned pack manifests, explicit local template sources, deterministic
parameter substitution, dry-run planning, preview diffs, clean-target apply
evidence, and release-readiness checks.

The primary reviewer workflow is:

1. List bundled and configured local template packs.
2. Inspect a template's source, compatibility, generated files, capabilities,
   parameters, generated schemas, and demo commands.
3. Validate a bundled template or local pack directory.
4. Dry-run template application to see planned creates, skips, conflicts,
   policy implications, and plan hash.
5. Preview safe relative diffs without mutating the target.
6. Apply a validated template to a clean empty target without approval.
7. Inspect `template_application.v1` evidence and workspace metadata.
8. Confirm generated config, task, policy, and eval examples validate.
9. Confirm release readiness rejects unsafe or incomplete template packs.

## Implemented in V7

The V7 target scope is local template packs:

- `template.v2.toml` pack manifests loaded with the Python standard library
- bundled template packs plus legacy bundled JSON templates
- configured local template directories through `config.v2`
- `--target` as the preferred apply destination option, with `--destination`
  retained as a compatibility alias
- `template pack validate <path>` for validating local pack directories
- deterministic `{{ param_name }}` substitution in file text and declared
  target paths
- parameter types `string`, `boolean`, `choice`, and `path_fragment`
- dry-run and preview-diff modes with no target file, run artifact, evidence,
  or workspace metadata mutation
- clean empty-target apply without approval after validation and policy checks
- non-empty target and overwrite mutation guarded by approval-bound planning
- `template_application.v1` evidence for actual applies
- bundled packs for `python-lib`, `cli-tool`, `fastapi-service`,
  `provider-audit`, and `retrieval-quality`
- release-readiness gates for bundled pack validation, dry-run, clean apply,
  generated schema validation, docs presence, and remote catalog default
  rejection

## Roadmap / Not implemented yet

The following are not part of V7:

- remote template catalogs
- template marketplace behavior
- template signing
- organization template catalogs
- cloud template registries
- enterprise template governance
- arbitrary hook execution
- script execution
- executable template lifecycle hooks
- conditional file inclusion
- loops, filters, expressions, includes, or a full template programming
  language
- environment reads, shell expansion, or remote reads during rendering
- `template create` or `template export`
- `eval.v2`

## User Stories

1. As a local developer, I want to list bundled and local template packs, so
   that I can find a workflow scaffold without searching package internals.
2. As a local developer, I want to inspect template metadata before applying a
   template, so that I understand generated files, compatibility, parameters,
   capabilities, and demo commands.
3. As a template author, I want to validate a local pack directory without
   installing it, so that I can catch manifest, file, placeholder, safety, and
   schema errors early.
4. As a reviewer, I want dry-run apply to report planned changes without
   mutation, so that I can review generated files, conflicts, capabilities,
   warnings, policy implications, and plan hash safely.
5. As a reviewer, I want preview diff to show safe relative diffs without
   mutation, so that I can inspect rendered changes before approval or apply.
6. As a local developer, I want clean empty-target apply to complete without
   approval, so that normal scaffolding stays ergonomic.
7. As a security reviewer, I want non-empty target mutation and overwrites to
   require approval-bound planning, so that existing repository state is not
   changed silently.
8. As a security reviewer, I want template validation to reject traversal,
   symlink escape, remote sources, hooks, scripts, secret-like values,
   generated citation markers, private uploaded-file references, binary files,
   and undeclared placeholders, so that template packs are not a hidden
   execution or data-leak surface.
9. As a maintainer, I want template application evidence, so that generated
   files, hashes, parameters, approvals, policy profile, diagnostics, and final
   status are auditable.
10. As a release reviewer, I want release readiness to exercise every bundled
    template pack, so that V7 can be accepted from a clean checkout.
11. As an existing user, I want current template IDs and legacy JSON template
    readability to remain stable, so that V7 does not break existing workflows.
12. As a documentation reviewer, I want docs to separate implemented local
    template-pack behavior from future remote or governance features, so that
    public claims stay aligned with tested behavior.

## Behavioral Requirements

1. `agent-harness template list` reports bundled packs, legacy bundled
   templates, and configured local packs.
2. Template list output includes template ID, version, source type,
   compatibility status, and diagnostics where applicable.
3. Invalid local packs are reported as diagnostics and are not usable.
4. Duplicate template IDs across discovered sources fail clearly.
5. `agent-harness template show <template-id>` displays source, compatibility,
   generated files, required capabilities, declared parameters, generated schema
   versions, demo commands, and diagnostics.
6. Current template IDs `python-lib`, `cli-tool`, and `fastapi-service` remain
   stable.
7. Legacy `template.v1` and bundled JSON template inputs remain readable where
   currently supported.
8. `agent-harness template apply <template-id> --target <path>` is the preferred
   apply interface.
9. `--destination <path>` remains a backward-compatible alias for `--target`.
10. Repeated `--param key=value` options provide template parameter values.
11. `template.v2.toml` is the preferred V7 pack manifest format.
12. The manifest loader uses `tomllib` and does not add a YAML dependency only
    for template manifests.
13. V7 compatibility uses simple `minimum_agent_harness_version` and
    `maximum_agent_harness_version` fields.
14. Unsupported arbitrary version expressions such as `>=1.4,<2.0`, `^1.4`,
    or `~1.4` are rejected clearly unless a future implementation adds an
    explicit range parser.
15. Template rendering supports only deterministic `{{ param_name }}`
    substitution.
16. Parameters may be substituted into file text and declared output paths.
17. Undeclared placeholders fail validation.
18. Unsupported placeholder syntax fails validation.
19. Missing required parameters fail clearly.
20. Choice parameters accept only declared values.
21. `path_fragment` parameters cannot traverse, be absolute, contain drive
    prefixes, or escape the target.
22. Rendering does not support conditionals, loops, filters, expressions,
    includes, function calls, environment reads, shell expansion, remote reads,
    or conditional file inclusion.
23. `config.v2` supports explicit local template directories under
    `templates.local_dirs`.
24. Existing `template_catalog: bundled` compatibility remains readable.
25. The template source loader does not scan arbitrary filesystem locations
    outside configured local directories and packaged bundled templates.
26. `agent-harness template validate <template-id>` and
    `agent-harness template pack validate <path>` use the same validator core.
27. Validation checks required manifest fields, manifest schema, template ID
    format, template version format, compatibility, included file existence,
    UTF-8 text-only content, path traversal, absolute paths, drive prefixes,
    symlink escapes, parent symlink traversal, unsupported placeholders,
    undeclared parameters, remote source declarations, hook/script
    declarations, generated citation markers, private uploaded-file
    references, credential-like literals, hidden or unlisted generated files,
    generated schema consistency, and generated example validity.
28. Validation returns actionable human-readable and machine-readable
    diagnostics.
29. `--dry-run` reports planned creates, planned skips, conflicts, schema
    versions, required capabilities, warnings, policy implications, generated
    files, and apply plan hash.
30. `--dry-run` does not write target files, persist run artifacts, persist
    template application evidence, or mutate workspace metadata.
31. `--preview-diff` reports safe relative diffs without mutation.
32. Preview diffs redact environment-like and secret-like content.
33. Path traversal and symlink escape are denied before diff generation.
34. Hidden or unlisted generated files are denied.
35. Applying to a clean empty target validates the pack, validates parameters,
    builds an apply plan, runs policy checks, performs two-pass planning, writes
    declared files only, persists evidence, updates workspace metadata, and
    validates generated examples.
36. Clean empty-target apply does not require approval by default.
37. Applying to a non-empty target is preview-only by default unless an
    approval-bound mutation path is used.
38. Direct file collisions stop by default.
39. `--force` may produce overwrite planning but must not write without
    approval.
40. Approval binding for non-empty or overwrite mutation includes template ID,
    template version, target path, planned file list, operation types, rendered
    content hashes, apply plan hash, policy profile, and checkpoint hash where
    applicable.
41. If clean apply fails during writing, files created by that operation are
    rolled back where safe and evidence does not claim success.
42. Actual applies persist `template_application.v1` evidence under
    `.agent-harness/template_applications/`.
43. Template application evidence records schema version, template ID, template
    version, source, target path, applied time, Agent Harness version,
    parameters, planned files, created files, skipped files, conflicts,
    operation types, rendered hashes, plan hash, approval requirement, approval
    ID, policy profile, diagnostics, and status.
44. Dry-run and preview emit the same evidence shape to stdout without
    persisting files.
45. Bundled V7 packs include `python-lib`, `cli-tool`, `fastapi-service`,
    `provider-audit`, and `retrieval-quality`.
46. Each bundled pack includes a README or docs fragment, generated config
    example, generated policy example, generated task example, generated eval
    example using `eval.v1`, demo metadata, schema-valid generated files, and
    at least one runnable validation or demo command where practical.
47. `examples/template_pack_system/` demonstrates the V7 golden path.
48. `agent-harness release readiness` validates all bundled packs, dry-runs all
    bundled packs, clean-applies all bundled packs to a temporary workspace,
    validates generated schemas, confirms template application evidence exists,
    confirms docs exist, and rejects remote catalog defaults.
49. V7 docs distinguish implemented local template-pack behavior from roadmap
    remote catalog, marketplace, signing, organization catalog, cloud registry,
    hook execution, script execution, enterprise governance, and conditional
    file inclusion behavior.
50. The V7 golden path works from a clean checkout:
    `template list`, `template show python-lib`, `template validate
    python-lib`, dry-run apply, preview-diff apply, clean apply, and
    `release readiness`.

## Implementation Decisions

- Preserve the existing `agent_harness.templates` package as the template
  ownership boundary, but deepen it around source discovery, manifest loading,
  validation, rendering, planning, applying, and evidence.
- Keep `agent_harness.core.runtime` as the run orchestration and approval
  integration boundary. It should coordinate template apply behavior without
  absorbing detailed pack parsing or validation logic.
- Keep `agent_harness.policy` as the shared gate for filesystem writes,
  capabilities, non-empty target mutation, and overwrite approval.
- Add `template.v2.toml` as the V7 pack manifest format and parse it with
  `tomllib`.
- Do not add PyYAML solely for template manifests.
- Use simple min/max compatibility fields instead of arbitrary semver ranges in
  V7.
- Extend `config.v2` with `templates.local_dirs` while preserving
  `template_catalog: bundled`.
- Treat local template metadata and contents as untrusted until validation
  succeeds.
- Use deterministic text substitution only. Rendering must not read
  environment variables, execute code, execute shell commands, or fetch remote
  content.
- Keep file inclusion manifest-static in V7. Parameters substitute values but
  do not conditionally include or exclude files.
- Store actual apply evidence as `template_application.v1` under
  `.agent-harness/template_applications/` and link it from run or workspace
  metadata where appropriate.
- Use current `eval.v1` for generated eval examples.
- Extend release readiness instead of creating a separate template-pack release
  command.
- Keep `--destination` as an alias while documenting `--target` as preferred.
- Keep remote catalogs, signing, marketplace behavior, org catalogs, cloud
  registries, hooks, scripts, template create/export, and enterprise governance
  outside V7.

## Testing Decisions

- Start implementation slices with failing public-interface tests and implement
  the minimum behavior needed to make each slice pass.
- Test template discovery through CLI behavior and public loader outputs rather
  than private helper functions.
- Test validation through `template validate` and `template pack validate`.
- Test dry-run and preview through CLI behavior and filesystem assertions that
  prove no mutation occurred.
- Test clean apply through generated files, workspace metadata, and
  `template_application.v1` evidence.
- Test non-empty and overwrite behavior through approval-bound run artifacts,
  not by bypassing the approval service.
- Add adversarial tests for traversal, absolute paths, drive-prefixed paths,
  symlink escape, parent symlink traversal, secret-like values, generated
  citation markers, private uploaded-file references, remote source
  declarations, undeclared placeholders, malicious path parameters, overwrite
  without force, force without approval, hidden or unlisted generated files, and
  hook/script declarations.
- Add release-readiness tests proving V7 fails when bundled packs lack
  validation, dry-run, clean apply, generated schema checks, docs, or evidence.
- Use behavior-oriented integration tests for generated config, task, policy,
  and eval example validation.

## Out of Scope

- Remote template catalogs.
- Template marketplace behavior.
- Template signing or signature verification.
- Organization template catalogs.
- Cloud template registries.
- Enterprise template governance.
- Arbitrary hook execution or script execution.
- Executable template lifecycle hooks.
- Conditional file inclusion.
- Loops, filters, expressions, includes, function calls, or a full template
  programming language.
- Environment reads, shell expansion, or remote reads during rendering.
- `template create`.
- `template export`.
- `eval.v2`.
- Adding a YAML dependency solely for V7 manifests.
- Adding arbitrary semver range parsing unless a future implementation decision
  explicitly justifies a dependency or parser.

## Further Notes

The highest-risk parts of V7 are path safety, symlink handling, mutation
semantics, approval binding, and docs claim drift. Those risks should drive the
first adversarial and integration tests.

V7 intentionally favors a small, deterministic rendering model over template
expressiveness. This keeps template packs inspectable and prevents them from
becoming a hidden execution surface.

The current repo has a bundled SQLite-backed template registry and legacy JSON
bundles. V7 should evolve that surface without breaking existing IDs or
compatibility paths.
