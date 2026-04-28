# Plan: Agent Harness V8 Skills System

> Source PRD: [docs/prd-agent-harness-v8.md](../docs/prd-agent-harness-v8.md)

V8 targets `v1.5.0`. This plan is written for PRD to plan to TDD execution:
each phase is a vertical tracer bullet, and each phase starts from one public
behavior test before implementation.

## Architectural Decisions

Durable decisions that apply across all phases:

- **Public interface**: add `agent-harness skill list/show/validate/render/resolve`
  and `agent-harness skill pack validate`; extend `run`, `inspect`, template
  metadata, and release readiness only where skill provenance needs to be
  visible.
- **Key models**: add public models for `skill.v1`, registry records, skill
  details, validation reports, resolution reports, context skill provenance,
  and `skill_manifest.v1`.
- **Schema**: extend `config.v2` with `skills.local_dirs`, `task.v2` with
  optional `skills`, and `template.v2` with optional `recommended_skills`.
- **Storage**: emit `skill_manifest.json` under the run directory and link it
  from summary artifacts and the artifact index.
- **Runtime boundary**: runtime coordinates resolution, context assembly,
  checkpointing, artifact emission, and inspectability; skill parsing,
  registry, validation, rendering, and hashing stay in `agent_harness.skills`.
- **Context boundary**: skill content is represented in the existing context
  manifest included/rejected item model with provenance and policy decision
  evidence.
- **Policy boundary**: policy remains the permission ceiling. Skills can be
  accepted or rejected as guidance but never loosen tools, paths, provider
  profiles, sensitivity classes, approvals, or provider input rules.
- **Template boundary**: templates may recommend skills and record those
  recommendations, but recommendations do not force runtime use by default.
- **Audit boundary**: every run that uses skills records source, version, hash,
  inclusion status, policy decision, and context manifest id.
- **External service boundary**: V8 uses only bundled and configured local skill
  sources.
- **Release boundary**: release readiness is the acceptance surface for bundled
  skill validation, resolution, manifests, context provenance, demo evidence,
  and docs scope checks.

---

## Phase 0: V8 Scope Is Documented And Guarded

**User stories covered**

- Story 10: documentation reviewer can distinguish local V8 behavior from
  deferred distribution and governance work.
- Story 12: existing users understand that current workflows remain stable
  unless skills are selected.

**Observable behaviors**

- V8 PRD and plan exist.
- Skills docs describe skills as workflow guidance, not tools, templates,
  policy, approvals, or code execution.
- Docs checks reject implemented-scope claims for deferred distribution,
  signing, hosted, and governance features.

**First RED test**

- `agent-harness docs check` passes while a current-capability doc claims an
  unsupported skill distribution feature as implemented behavior.

### What to build

Add the durable V8 docs and docs-check guarded phrases before implementation
starts. Update README, roadmap, architecture, security model, and release
readiness docs only enough to state the local V8 scope and keep deferred
features in the correct section.

### Acceptance criteria

- [ ] `docs/prd-agent-harness-v8.md` exists and follows the PRD template.
- [ ] `plans/agent-harness-v8.md` exists and uses vertical slices.
- [ ] `docs/skills-system.md` describes V8 local skills.
- [ ] README and roadmap describe V8 without claiming deferred features.
- [ ] Architecture docs identify `agent_harness.skills` as the skill-system
      boundary.
- [ ] Security docs state that skills cannot grant tools, widen policy,
      approve actions, execute code, or mutate files.
- [ ] Release-readiness docs name the V8 skill gates.
- [ ] Docs check rejects unsupported skill claims outside roadmap sections.
- [ ] Docs check passes after docs are corrected.

### Out of scope

- Skill schema implementation.
- Skill registry behavior.
- Runtime skill resolution.

---

## Phase 1: Reviewer Can Validate One Bundled Skill

**User stories covered**

- Story 2: developer can inspect skill metadata.
- Story 3: skill author can validate schema, compatibility, body, and safety.
- Story 7: security reviewer can reject authority-expanding skill content.

**Observable behaviors**

- A bundled `write-a-prd` `SKILL.md` can be parsed and validated.
- Invalid frontmatter, missing body, unsupported schema, unsafe markers, and
  authority-expanding declarations fail with clear diagnostics.
- A deterministic skill hash is reported for the valid skill.

**First RED test**

- `agent-harness skill validate write-a-prd` fails because there is no
  `skill.v1` model, validator, bundled skill source, or deterministic hash.

### What to build

Create the minimal `agent_harness.skills` boundary needed to parse `SKILL.md`
frontmatter plus body, validate `skill.v1`, compute a deterministic hash, and
load one bundled skill from package data. Keep validation reusable for direct
paths and registry-loaded skills.

### Acceptance criteria

- [ ] `skill.v1` required fields validate.
- [ ] Optional fields validate when present.
- [ ] `skill_id` is stable and URL/path safe.
- [ ] `version` is semantic-version-like.
- [ ] Body and description must be non-empty.
- [ ] Unsupported future schema versions fail clearly.
- [ ] Missing required fields fail clearly.
- [ ] Compatibility ranges including `>=1.5.0,<2.0.0` are evaluated.
- [ ] Unsupported compatibility expressions fail clearly.
- [ ] Generated citation markers, private uploaded-file references, and
      secret-like values fail validation.
- [ ] Attempts to declare tools, approvals, provider changes, policy changes,
      file mutation, code execution, or network calls fail validation.
- [ ] Hashes are deterministic across repeated validation.

### Out of scope

- Listing multiple skills.
- Local skill directories.
- Task resolution.
- Runtime context inclusion.

---

## Phase 2: Reviewer Can List, Show, Render, And Pack-Validate Skills

**User stories covered**

- Story 1: developer can discover available skills.
- Story 2: developer can inspect and render a skill.
- Story 3: skill author can validate a local pack directory.

**Observable behaviors**

- `skill list` shows all four bundled skills.
- `skill show prd-plan-tdd-workflow` displays metadata, source, compatibility,
  validation status, and hash.
- `skill render prd-plan-tdd-workflow` prints resolved Markdown for inspection.
- `skill pack validate <path>` validates all `SKILL.md` files under a local
  directory without installing them.

**First RED test**

- `agent-harness skill list` cannot report the required bundled skills with
  source and validation status.

### What to build

Add bundled skill discovery, skill detail loading, render output, and
pack-validation output. Add package data for the four required bundled skills.
Keep CLI output simple and consistent with the existing argparse style.

### Acceptance criteria

- [ ] Bundled skills are available from a clean install.
- [ ] Required bundled skills are `write-a-prd`, `prd-to-plan`, `tdd`, and
      `prd-plan-tdd-workflow`.
- [ ] `skill list` reports id, version, name, source type, compatibility,
      validation status, and description.
- [ ] `skill show` reports metadata, source, hash, compatibility, validation
      diagnostics, and body summary.
- [ ] `skill render` outputs inspectable Markdown with metadata context.
- [ ] `skill validate <skill-id>` validates a registry skill.
- [ ] `skill validate <path>` validates a direct `SKILL.md` path.
- [ ] `skill pack validate <path>` validates every skill in a local pack
      directory.
- [ ] Pack validation does not install, copy, execute, or mutate skills.
- [ ] Invalid bundled skills fail release-oriented validation.

### Out of scope

- Configured local skill directories.
- Duplicate handling across sources.
- Runtime skill artifacts.

---

## Phase 3: Local Skill Discovery Is Explicit And Deterministic

**User stories covered**

- Story 1: developer can list local skills.
- Story 3: skill author gets diagnostics for invalid local skills.
- Story 7: security reviewer can trust invalid local skills are not usable.

**Observable behaviors**

- `config.v2` `skills.local_dirs` controls local discovery.
- Valid local skills appear in `skill list`.
- Invalid local skills appear with diagnostics and cannot be shown, rendered, or
  resolved as usable guidance.
- Duplicate ids fail deterministically without silent shadowing.

**First RED test**

- A local skill with the same id as a bundled skill silently shadows the bundled
  skill or resolves inconsistently.

### What to build

Extend config with explicit local skill directories, load local `SKILL.md`
files only from configured locations, validate before use, and make duplicate
id handling deterministic. Support `~` expansion for user-local skill
configuration while keeping project-relative directories normalized.

### Acceptance criteria

- [ ] `config.v2` accepts `skills.local_dirs`.
- [ ] Existing configs without `skills` remain valid.
- [ ] Local skills are discovered only from configured directories.
- [ ] Missing configured directories are reported without crashing list output.
- [ ] Invalid local skills are visible as invalid records with diagnostics.
- [ ] Invalid local skills cannot be rendered or resolved as usable.
- [ ] Duplicate local ids fail clearly.
- [ ] Local ids cannot shadow bundled ids silently.
- [ ] Source type and source path are recorded for local skills.

### Out of scope

- Task spec resolution.
- Template recommendations.
- Runtime artifacts.

---

## Phase 4: Tasks And Templates Resolve Skills Without Forcing Authority

**User stories covered**

- Story 4: task author can request skills.
- Story 5: template author can recommend skills.
- Story 7: security reviewer can verify selection does not widen policy.
- Story 12: existing task behavior remains stable unless skills are selected.

**Observable behaviors**

- `skill resolve --task examples/skills_workflow/task.yaml` resolves task
  requested skills.
- Template-recommended skills are recorded as recommendations and reported
  missing when unresolved.
- Unknown or invalid task-requested skills fail clearly.
- Resolution output records requested-by evidence, source, version, hash, and
  diagnostics.

**First RED test**

- A task containing `skills: [prd-plan-tdd-workflow]` validates or runs without
  any skill resolution evidence.

### What to build

Extend `task.v2`, `template.v2`, template detail, template application
evidence, and workspace metadata with skill selection and recommendation data.
Implement a resolver that merges task-requested and template-recommended skill
evidence while treating only explicit task requests as required for runtime use.

### Acceptance criteria

- [ ] `task.v2` accepts `skills`.
- [ ] `task.v1` rejects or ignores `skills` only through an explicit
      compatibility decision.
- [ ] Unknown task-requested skill ids fail clearly.
- [ ] Invalid task-requested skills fail clearly.
- [ ] Resolution records source, version, hash, and requested-by evidence.
- [ ] `template.v2` accepts optional `recommended_skills`.
- [ ] `template show` displays recommended skills when present.
- [ ] Template application evidence records recommended skills.
- [ ] Workspace metadata records recommended skills from applied templates.
- [ ] Missing template-recommended skills are reported as diagnostics.
- [ ] Template recommendations do not force runtime skill usage by default.
- [ ] Resolution cannot add tools, approvals, policy changes, or provider
      changes to the effective task.

### Out of scope

- Context manifest inclusion.
- `skill_manifest.v1` run artifact emission.
- Eval assertions for skills.

---

## Phase 5: Skill Guidance Enters Context Through Policy

**User stories covered**

- Story 6: agent operator can include skill guidance through policy-aware
  context assembly.
- Story 7: security reviewer can verify rejected skills and authority limits.
- Story 8: release reviewer can audit inclusion status and policy decisions.

**Observable behaviors**

- Running a task with `prd-plan-tdd-workflow` creates a context manifest entry
  for the accepted skill.
- A rejected skill appears in rejected context manifest evidence without body
  text.
- Policy decisions for skill inclusion are emitted as run events.

**First RED test**

- A task-requested skill is resolved but absent from `context_manifest.json`, or
  rejected skill body text leaks into rejected manifest evidence.

### What to build

Extend context assembly to accept resolved skill content as guidance sources.
Represent included and rejected skill guidance using public context models with
skill provenance. Add a policy decision path that checks validation,
compatibility, allowed context classes, and context sensitivity without letting
the skill change policy.

### Acceptance criteria

- [ ] Accepted skills are represented in `context_manifest.json`.
- [ ] Skill manifest items include skill id, version, source, hash, inclusion
      mode, and policy decision id.
- [ ] Rejected skills are represented with rejection reason and no body text.
- [ ] Skill content hash is deterministic.
- [ ] Policy decision events are recorded for skill inclusion.
- [ ] Bundled skills are classified consistently.
- [ ] Local skills have a conservative default context class.
- [ ] `allowed_context_classes` can reject an otherwise valid skill.
- [ ] Skills cannot change effective policy, tools, provider profile,
      sensitivity classes, write roots, read roots, or approval rules.
- [ ] Provider input treats accepted skill guidance as context evidence, not
      authority.

### Out of scope

- Persisting `skill_manifest.v1`.
- Inspect output changes.
- Release readiness checks.

---

## Phase 6: Runs Emit Inspectable Skill Manifests

**User stories covered**

- Story 8: release reviewer can audit exact skill usage.
- Story 9: operator can inspect skills from run output.
- Story 11: workflow reviewer can verify the PRD to plan to TDD guidance path.

**Observable behaviors**

- Runs that use skills emit `skill_manifest.json`.
- Summary artifacts and artifact index link the skill manifest.
- `inspect run` includes skill manifest evidence.
- Evals can assert expected skill ids.

**First RED test**

- A dry-run task using `prd-plan-tdd-workflow` completes without a
  `skill_manifest.json` artifact linked from summary artifacts.

### What to build

Emit `skill_manifest.v1` after context manifest creation so it can reference
the context manifest id and policy decisions. Add summary/artifact-index links,
inspect output, export/eval integration where existing artifact flows require
it, and operator artifact allowlisting if the local API exposes run detail
artifact statuses.

### Acceptance criteria

- [ ] Runs using skills emit `skill_manifest.json`.
- [ ] `skill_manifest.v1` records run id and task id.
- [ ] Each skill record includes id, version, source, hash, requested-by
      evidence, resolution time, inclusion status, policy decision id, and
      context manifest id.
- [ ] Summary artifacts include `skill_manifest`.
- [ ] Artifact index includes the skill manifest hash.
- [ ] `inspect run` includes `skill_manifest` when present.
- [ ] Runs without skills continue without a skill manifest.
- [ ] Evals can verify expected skills were used.
- [ ] Dry-run and non-dry-run paths record equivalent skill provenance.
- [ ] Security-gated runs that stop before context assembly do not claim skills
      were included.

### Out of scope

- New skill creation/export commands.
- New hosted inspection surfaces.
- Network distribution behavior.

---

## Phase 7: Demo And Release Readiness Close V8

**User stories covered**

- Story 8: release reviewer can accept skill evidence from a clean checkout.
- Story 10: docs stay aligned with implemented behavior.
- Story 11: workflow reviewer can run the PRD to plan to TDD demo.

**Observable behaviors**

- `examples/skills_workflow/` demonstrates the V8 golden path.
- Release readiness validates bundled skills and verifies skill resolution,
  context provenance, manifest emission, docs, and demo evidence.
- The final acceptance command path works from a clean checkout.

**First RED test**

- `agent-harness release readiness` passes while a bundled skill is invalid or
  while the skills workflow demo fails to produce skill manifest evidence.

### What to build

Add the skills workflow example and expected artifacts. Extend release readiness
to run or verify bundled skill validation, registry behavior, task resolution,
dry-run manifest emission, context provenance, inspectability, docs, and
deferred-scope claim guards.

### Acceptance criteria

- [ ] `examples/skills_workflow/README.md` documents the V8 golden path.
- [ ] `examples/skills_workflow/task.yaml` references
      `prd-plan-tdd-workflow`.
- [ ] Expected example `skill_manifest` and `context_manifest` artifacts exist.
- [ ] Demo workspace includes a feature brief for the skill-guided workflow.
- [ ] Release readiness validates all bundled skills.
- [ ] Release readiness verifies skill list/show/validate/resolve behavior.
- [ ] Release readiness verifies dry-run skill manifest emission.
- [ ] Release readiness verifies context manifest skill provenance.
- [ ] Release readiness verifies inspect output includes skills.
- [ ] Release readiness verifies skills docs exist.
- [ ] Release readiness verifies docs keep deferred distribution and governance
      features out of implemented sections.
- [ ] Final acceptance path works:
      `uv sync`,
      `uv run agent-harness skill list`,
      `uv run agent-harness skill show prd-plan-tdd-workflow`,
      `uv run agent-harness skill validate prd-plan-tdd-workflow`,
      `uv run agent-harness skill resolve --task examples/skills_workflow/task.yaml`,
      `uv run agent-harness run examples/skills_workflow/task.yaml --dry-run`,
      `uv run agent-harness inspect <run-id>`,
      and `uv run agent-harness release readiness`.

### Out of scope

- Release tagging.
- Package publishing.
- Optional `skill create`.
- Optional `skill export`.

## Cross-Phase Invariants

- Skills are workflow guidance, not tools, templates, policy, approvals, or
  executable code.
- Skills never widen the selected policy profile.
- Skills never grant tools, approve actions, alter provider profiles, mutate
  files, change sensitivity classes, or introduce network calls.
- Local skill content is untrusted until validation succeeds.
- Invalid skills are reported with diagnostics and are not usable as accepted
  guidance.
- Rejected skill body text does not leak into rejected context evidence.
- Skill hashes are deterministic and recorded wherever skill content is used.
- Context manifests record both accepted and rejected skill decisions.
- Template recommendations are recommendations, not forced runtime skill usage.
- Task-requested skills are required and fail clearly when unknown or invalid.
- Runs without selected skills keep existing behavior.
- Tests verify behavior through CLI commands, public models, persisted
  artifacts, inspect output, and release reports rather than private helper
  details.
- Each implementation phase starts with one public failing behavior test and
  refactors only after that behavior is green.
