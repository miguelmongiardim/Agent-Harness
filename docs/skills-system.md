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
template-recommended skill evidence. Context inclusion, run artifacts, and
release-readiness evidence are later V8 slices and should not be described as
current behavior until their tests and implementation land.

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

## V8 Local Skill Boundary

V8 introduces local Markdown skills as reusable workflow guidance.
A skill is an inspectable `SKILL.md` file with `skill.v1` YAML frontmatter and
a Markdown body. Skills explain how to perform a workflow; they are not tools,
templates, policies, approvals, provider profiles, or executable code.

The `agent_harness.skills` boundary owns current registry, validation, and
task/template resolution behavior and will own later manifest behavior:

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

Accepted skill guidance must enter runs through the same policy-aware context
assembly path used for other context evidence. Rejected skill guidance must be
recorded without leaking body text into rejected manifest evidence.

## Planned Reviewer Workflow

The V8 implementation plan proves the skills system through these public
behaviors:

- list bundled and configured local skills
- inspect skill metadata, source, compatibility, validation status, and hash
- validate a bundled skill, direct `SKILL.md`, or local skill pack
- render deterministic Markdown for review
- resolve task-requested skills and template recommendations without widening
  task or policy authority
- include accepted skill guidance in context manifests with policy provenance
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
