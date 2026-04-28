# Skills System

## Status

V8 is the `v1.5.0` skills-system track. The durable source documents are the
[V8 PRD](prd-agent-harness-v8.md) and
[V8 implementation plan](../plans/agent-harness-v8.md).

Phase 0 added documentation scope and docs-check guards. Phase 1 added the
first validation slice for `agent-harness skill validate write-a-prd` and
direct `SKILL.md` validation. Phase 2 added bundled skill discovery, skill
inspection, rendered Markdown review, and local skill-pack validation. Phase 3
added explicit configured local skill discovery through `config.v2`
`skills.local_dirs`. Phase 4 adds task-requested skill resolution and
template-recommended skill evidence. Phase 5 adds policy-gated skill guidance
inside run context manifests. Phase 6 adds `skill_manifest.v1` run artifacts,
summary and artifact-index links, inspect output, operator run-detail evidence,
and eval assertions for expected skill usage. Phase 7 adds the
`examples/skills_workflow/` demo and release-readiness gates for bundled skill
validation, registry commands, resolution, dry-run manifest evidence, inspect
output, skills docs, and deferred-scope docs checks.

## Current Capabilities

The current implementation provides:

- bundled skills for `write-a-prd`, `prd-to-plan`, `tdd`, and
  `prd-plan-tdd-workflow`
- configured local skill directories through `config.v2` `skills.local_dirs`,
  including project-relative paths and `~` expansion for user-local paths
- `agent-harness skill list` with id, version, name, source type,
  compatibility, validation status, and description
- `agent-harness skill show <skill-id>` with metadata, source, hash,
  compatibility, diagnostics, and body summary
- `agent-harness skill render <skill-id>` with a Markdown metadata header and
  skill body
- `agent-harness skill validate write-a-prd` for bundled skill validation
- `agent-harness skill resolve --task <task.yaml>` for resolving `task.v2`
  requested skills and applied-template recommendations
- direct `SKILL.md` validation through the same command when the argument is an
  existing path
- `agent-harness skill pack validate <path>` for read-only validation of every
  `SKILL.md` under a local directory
- `task.v2` `skills` requests; `task.v1` rejects skill requests explicitly
- `template.v2` `recommended_skills` metadata visible through `template show`
- template application evidence and workspace metadata recording recommended
  skills from applied templates
- resolution diagnostics for unknown or invalid task-requested skills
- missing template-recommended skills reported as non-required diagnostics
- resolution evidence for source, version, hash, requested-by records, and
  unchanged task authority fields
- `agent-harness run <task> --dry-run` includes task-requested, resolved skills
  in `context_manifest.json` as policy-mediated guidance
- accepted skill context items record skill id, version, source, deterministic
  hash, inclusion mode, policy decision id, and body text
- rejected skill context items record the skill id, source, hash, rejection
  reason, and policy decision id without persisting body text
- bundled skill guidance is classified as public context; configured local
  skill guidance defaults to an internal context class
- policy `allowed_context_classes` and skill metadata can reject valid guidance
  without widening task or policy authority
- provider input treats accepted skill guidance as context evidence linked to a
  context manifest item
- runs that use task-requested skills emit `skill_manifest.json` with run id,
  task id, context manifest id, skill id, version, source type, source, hash,
  requested-by records, resolution time, inclusion status, policy decision id,
  and context manifest item id
- run summaries and `artifact-index.json` link `skill_manifest`; the artifact
  index records its hash
- `agent-harness inspect run <run-id>` includes `skill_manifest` when present
- local operator run detail includes `skill_manifest` when present
- `eval.v1` accepts `expected_skills` so evals can verify included skills from
  recorded `skill_manifest` evidence
- runs without selected skills do not emit a skill manifest
- security-gated runs that stop before context assembly do not claim skill
  inclusion
- missing configured local skill directories reported to stderr without
  crashing `skill list`
- duplicate skill ids rejected clearly, including local-to-local duplicates and
  local ids that would shadow bundled ids
- invalid configured local skills listed as failed records with diagnostics
  available through `skill show`
- valid configured local skills rendered only after validation succeeds
- local skill records include `source_type: local` and a recorded source path;
  paths under the project are project-relative, while user-local paths outside
  the project are absolute
- `skill.v1` frontmatter validation for required fields, optional fields,
  version format, skill id format, compatibility expressions, non-empty
  description, and non-empty Markdown body
- deterministic skill hashes for valid skills
- diagnostics for unsupported schemas, missing fields, unsafe content markers,
  and authority-expanding skill content or metadata
- a docs-check guard that rejects implemented-scope claims for unsupported skill
  distribution and governance features
- `examples/skills_workflow/` as the V8 skill-guided golden path
- release readiness gates for required bundled skill validation, skill
  list/show/validate behavior, task resolution, context manifest skill
  provenance, `skill_manifest.v1`, inspect output, skills docs, and demo files

## V8 Local Skill Boundary

V8 introduces local Markdown skills as reusable workflow guidance.
A skill is an inspectable `SKILL.md` file with `skill.v1` YAML frontmatter and
a Markdown body. Skills explain how to perform a workflow; they are not tools,
templates, policies, approvals, provider profiles, or executable code.

The `agent_harness.skills` boundary owns current registry, validation, and
task/template resolution and skill-manifest behavior:

- bundled and configured local skill discovery
- frontmatter and body parsing
- validation diagnostics
- deterministic skill hashing
- rendered Markdown inspection
- task-requested skill resolution
- template-recommended skill resolution diagnostics
- skill manifest construction

Runtime orchestration should coordinate resolved skill guidance with context
assembly, checkpoints, artifacts, and inspect output without absorbing parsing,
validation, hashing, or registry details.

## Policy And Security Boundary

Skills remain guidance only. They cannot grant tools, widen policy, approve
actions, alter provider profiles, change sensitivity classes, execute code,
mutate files, read environment variables, fetch network content, or bypass
context policy. Local skill content is untrusted until validation succeeds.

Accepted skill guidance enters runs through the same policy-aware context
assembly path used for other context evidence. Rejected skill guidance is
recorded without leaking body text into rejected manifest evidence. Provider
input can include accepted skill guidance as evidence, but the skill record does
not alter effective policy, tools, provider profile, sensitivity classes, roots,
or approval rules.

## Planned Reviewer Workflow

The V8 implementation plan proves the skills system through these public
behaviors:

- list bundled and configured local skills
- inspect skill metadata, source, compatibility, validation status, and hash
- validate a bundled skill, direct `SKILL.md`, or local skill pack
- render deterministic Markdown for review
- resolve task-requested skills and template recommendations without widening
  task or policy authority
- include accepted and rejected skill guidance in context manifests with policy
  provenance
- emit `skill_manifest.v1` run evidence
- show skill evidence through `inspect run`
- validate bundled skills and demo evidence through release readiness

## Guarded Scope

The V8 docs-check guard rejects implemented-scope claims that skills already
provide remote skill catalogs, skill marketplaces, skill signing, hosted skill
services, enterprise skill registries, organization-wide skill governance,
centralized skill governance, or skill installation from network locations.

Those phrases are valid only in roadmap, out-of-scope, not-implemented, or
future sections, or when the sentence explicitly denies support.

## Roadmap / Not Implemented Yet

Remote skill catalogs, skill marketplace behavior, signed skill distribution,
enterprise skill registries, organization-wide skill governance, remote skills,
hosted skill services, automatic code execution from skills, skill installation
from network locations, centralized skill governance policy, skill signing,
`skill create`, and `skill export` remain outside the V8 implementation target.
