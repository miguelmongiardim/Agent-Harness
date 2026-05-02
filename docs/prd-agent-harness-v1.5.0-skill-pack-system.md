# PRD: Agent Harness v1.5.0 Skill Pack System

## Problem Statement

Agent Harness has strong local controls for tasks, policy, context manifests,
templates, approvals, runs, exports, and release evidence. What it does not yet
have is a first-class way to manage reusable workflow procedures as inspectable
artifacts.

Without v1.5.0, reusable procedures such as writing a PRD, converting that PRD into
vertical implementation slices, and executing those slices with TDD remain
informal prompt text. That weakens auditability because a reviewer cannot list,
inspect, validate, resolve, hash, include, or reject workflow guidance with the
same discipline already applied to templates, context, policy, and run
artifacts.

The affected users are local developers, maintainers, release reviewers,
template authors, security reviewers, and agent operators who need to know which
workflow instructions guided a task, whether those instructions were validated,
and whether they stayed inside the active policy ceiling.

## Solution

v1.5.0 targets `v1.5.0` and introduces the Skill Pack System: local, versioned,
validated Markdown workflow instructions with YAML frontmatter and deterministic
provenance. A skill is workflow guidance. It is not a tool, not a template, not
policy, not approval authority, and not executable code.

The primary reviewer workflow is:

1. List bundled and configured local skills.
2. Inspect a skill's metadata, source, compatibility, declared capabilities,
   allowed context classes, hash, and body summary.
3. Validate a bundled skill, local skill, or local skill pack directory.
4. Resolve skills requested by a task and recommended by applied template
   metadata.
5. Include accepted skill guidance in the context manifest through the same
   policy-aware context assembly model used for other context.
6. Record skill provenance, exact version, source, hash, policy decision, and
   inclusion status in run artifacts.
7. Inspect a run and verify which skills guided it.
8. Run a local demo showing the PRD to plan to TDD workflow through skills.
9. Confirm release readiness rejects missing, invalid, unsafe, or undocumented
   skills behavior.

The initial bundled skills are:

- `write-a-prd`
- `prd-to-plan`
- `tdd`
- `prd-plan-tdd-workflow`

These bundled skills define the PRD to plan to TDD workflow and must remain
repo-agnostic.

## Implemented in v1.5.0

The v1.5.0 target scope includes:

- `SKILL.md` files with `skill.v1` YAML frontmatter and Markdown body
- bundled skills shipped with Agent Harness
- configured local skill directories through `config.v2`
- task-requested skills through `task.v2`
- template-recommended skills through optional `template.v2` metadata
- `agent-harness skill list`
- `agent-harness skill show <skill-id>`
- `agent-harness skill validate <skill-id-or-path>`
- `agent-harness skill render <skill-id>`
- `agent-harness skill resolve --task <task.yaml>`
- `agent-harness skill pack validate <path>`
- deterministic skill hashes from normalized metadata and body
- validation diagnostics for schema, body, compatibility, safety, and authority
  boundaries
- policy-aware context manifest inclusion and rejection evidence
- `skill_manifest.v1` run artifacts
- inspect output showing skills used by a run
- release-readiness checks for bundled skills, resolution, manifests, context
  provenance, docs, and demo evidence
- an `examples/skills_workflow/` golden path

## Roadmap / Not implemented yet

The following are not part of v1.5.0:

- remote skill catalogs
- skill marketplace
- signed skill distribution
- enterprise skill registry
- organization-wide skill governance
- remote skills
- hosted skill service
- automatic code execution from skills
- skill installation from network locations
- centralized skill governance policy
- skill signing or signature verification

## User Stories

1. As a local developer, I want to list bundled and local skills, so that I can
   discover available workflow procedures without searching package internals.
2. As a local developer, I want to inspect a skill before using it, so that I
   can understand its purpose, metadata, compatibility, capabilities, context
   class limits, source, and hash.
3. As a skill author, I want to validate a local skill or skill pack before use,
   so that schema, body, compatibility, and safety issues are caught early.
4. As a task author, I want to request skills from a task spec, so that a run can
   resolve the exact workflow guidance intended for the task.
5. As a template author, I want templates to recommend skills, so that generated
   workspaces can advertise useful workflow procedures without forcing runtime
   use.
6. As an agent operator, I want accepted skill content to appear in context only
   after policy-aware assembly, so that workflow guidance cannot bypass policy.
7. As a security reviewer, I want skills to be unable to grant tools, widen
   policy, approve actions, alter provider profiles, change sensitivity rules,
   execute code, mutate files, or introduce network calls, so that skills remain
   guidance rather than authority.
8. As a release reviewer, I want run artifacts to record skill id, version,
   source, hash, inclusion status, policy decision, and context manifest id, so
   that skill usage is auditable.
9. As an operator using inspect, I want run inspection to show skills used and
   skill manifest evidence, so that review does not require manually browsing
   artifact directories.
10. As a documentation reviewer, I want docs to distinguish v1.5.0 local skills from
    future distribution and governance features, so that public claims stay
    aligned with implemented behavior.
11. As a workflow reviewer, I want a demo showing `prd-plan-tdd-workflow`
    resolving and entering run artifacts, so that v1.5.0 proves reusable workflow
    guidance end to end.
12. As an existing user, I want current task, policy, context, provider,
    template, approval, and run behavior to keep working unless a task opts into
    skills, so that v1.5.0 does not break existing workflows.

## Behavioral Requirements

1. `agent-harness skill list` reports bundled skills and configured local skills.
2. Skill list output includes skill id, version, name, source type,
   compatibility status, validation status, and a concise description.
3. Invalid local skills are reported with diagnostics and are not usable for
   resolution or runtime context.
4. Duplicate skill ids are handled deterministically; local skills cannot shadow
   bundled skills silently.
5. `agent-harness skill show <skill-id>` displays metadata, source, validation
   status, compatibility status, deterministic hash, and body summary.
6. `agent-harness skill render <skill-id>` outputs the resolved Markdown body
   and metadata header for direct inspection.
7. `agent-harness skill validate <skill-id-or-path>` validates a registry skill
   or a direct `SKILL.md` path and returns clear diagnostics.
8. `agent-harness skill pack validate <path>` validates every `SKILL.md` in a
   local pack directory without installing or copying the pack.
9. `skill.v1` requires `schema_version`, `skill_id`, `name`, `version`,
   `description`, `category`, `compatible_agent_harness_versions`, and
   `required_capabilities`.
10. Optional skill fields are `allowed_context_classes`,
    `default_policy_profile`, `related_skills`, `output_artifacts`,
    `validation_commands`, and `examples`.
11. Unsupported future skill schema versions fail clearly.
12. Missing required fields fail clearly.
13. `skill_id` values must be stable and URL/path safe.
14. `version` values must be semantic-version-like.
15. `description` and Markdown body must be non-empty.
16. Compatibility ranges such as `>=1.5.0,<2.0.0` are accepted for v1.5.0 skills.
17. Unsupported compatibility expressions fail clearly.
18. Skill hashes are computed deterministically from normalized frontmatter and
    body.
19. Validation rejects generated citation markers.
20. Validation rejects private uploaded-file references.
21. Validation rejects obvious secret-like values.
22. Validation rejects declarations that attempt to grant tools, approve
    actions, alter provider profiles, change policy, change sensitivity
    classes, write files, execute code, or introduce network calls.
23. `config.v2` supports `skills.local_dirs` as explicit local skill sources.
24. Task specs may request skills through `task.v2` `skills`.
25. `task.v1` inputs cannot use skills unless migrated through an explicit
    compatibility decision.
26. Unknown task-requested skills fail clearly.
27. Invalid task-requested skills fail clearly.
28. Template metadata may recommend skills through `recommended_skills`.
29. Template application records recommended skills in workspace metadata and
    application evidence.
30. Template recommendations do not force runtime skill usage unless the task
    explicitly requests them or a later explicit configuration says so.
31. Missing template-recommended skills are reported clearly without pretending
    they were included.
32. `agent-harness skill resolve --task <task.yaml>` resolves requested skills,
    validates them, records source/version/hash, and emits resolution evidence.
33. Runtime dry-run uses the same resolution behavior as the CLI resolver.
34. Skill content enters context only after policy evaluation.
35. Accepted skills appear in the context manifest with skill id, version,
    source, hash, policy decision id, and inclusion mode.
36. Rejected skills appear in the context manifest with rejection reason and no
    body text.
37. Skill content is treated as workflow guidance and untrusted evidence, not as
    policy authority.
38. Skills cannot widen allowed tools, write roots, read roots, provider input
    policy, provider trust policy, approval requirements, context sensitivity
    rules, or provider profiles.
39. Runs using skills emit `skill_manifest.v1`.
40. `skill_manifest.v1` records run id, task id, skills used, skill id, skill
    version, skill source, skill hash, resolution time, inclusion status, policy
    decision id, and context manifest id.
41. Run summaries include a skills-used summary and link the skill manifest
    artifact.
42. `agent-harness inspect run <run-id>` shows the skill manifest when present.
43. Evals can assert that expected skills were used.
44. Release readiness validates all bundled skills.
45. Release readiness verifies skill registry, skill resolution, skill manifest
    emission, context manifest provenance, docs presence, and demo evidence.
46. The v1.5.0 golden path works from a clean checkout:
    `skill list`, `skill show prd-plan-tdd-workflow`,
    `skill validate prd-plan-tdd-workflow`,
    `skill resolve --task examples/skills_workflow/task.yaml`,
    `run examples/skills_workflow/task.yaml --dry-run`, `inspect <run-id>`, and
    `release readiness`.

## Implementation Decisions

- Add `agent_harness.skills` as the ownership boundary for skill loading,
  frontmatter parsing, validation, registry discovery, rendering, resolution,
  hashing, and skill-manifest construction.
- Keep `agent_harness.core.runtime` as the orchestration boundary. Runtime
  should coordinate skill resolution, context inclusion, checkpoints, artifact
  links, and inspectable run evidence without absorbing validator or registry
  details.
- Keep `agent_harness.context` as the context manifest assembly boundary. Skill
  context entries should integrate with the existing included/rejected manifest
  model rather than creating an unrelated context artifact.
- Keep `agent_harness.policy` as the shared gate for skill context inclusion and
  authority boundaries. Skills are never a policy input that can loosen the
  selected profile.
- Extend existing public schema models rather than creating untracked ad hoc
  dictionaries for task skills, config skill directories, template
  recommendations, workspace metadata, context provenance, and skill manifests.
- Use `SKILL.md` with YAML frontmatter and Markdown body. Keep parsing local and
  deterministic; do not add a broad dependency only for skill frontmatter unless
  implementation proves the existing simple YAML subset is insufficient.
- Use compatibility range support for `compatible_agent_harness_versions`
  because v1.5.0 skill metadata requires version ranges, unlike v1.4.0 template packs.
- Store bundled skills under package data so they are available from clean
  installs.
- Treat local skill content as untrusted until validation succeeds.
- Use deterministic body rendering only. Rendering must not execute code, read
  environment variables, run commands, fetch data, or mutate files.
- Record skill source types distinctly enough to distinguish bundled skills,
  local configured skills, task-requested skills, and template-recommended
  skills in resolution and run evidence.
- Extend release readiness rather than adding a separate release command.
- Keep optional `skill create` and `skill export` outside v1.5.0 unless a later plan
  explicitly pulls them in.

## Testing Decisions

- Start each implementation slice with one failing public behavior test, then
  implement only enough to pass that behavior.
- Test schema validation through public models and CLI validation output.
- Test discovery through `skill list` and public registry APIs.
- Test `show`, `render`, `validate`, `pack validate`, and `resolve` through CLI
  behavior.
- Test runtime integration through dry-run artifacts, context manifests, skill
  manifests, summary artifacts, and inspect output.
- Test template recommendations through template detail, template application
  evidence, and workspace metadata.
- Test policy behavior by proving skill content cannot widen policy or grant
  authority, not by testing private helper names.
- Add adversarial tests for attempts to grant tools, approve actions, override
  policy, change provider profiles, change sensitivity classes, reference
  denied files, execute code, mutate files, introduce network calls, use
  generated citation markers, reference uploaded files, include secret-like
  values, use path traversal, collide skill ids, use malformed frontmatter, and
  declare unsupported future schemas.
- Add integration tests for bundled skill discovery, local skill discovery,
  skill resolution from task specs, context manifest inclusion and rejection,
  `skill_manifest.v1` emission, inspect output, eval assertions, and release
  readiness checks.
- Add E2E coverage for `examples/skills_workflow/` and the v1.5.0 golden path.
- Run the smallest relevant checks first during implementation, then broaden to
  unit, integration, adversarial, E2E, docs check, and release readiness.

## Out of Scope

- Network-based skill discovery.
- Marketplace installation flows.
- Signature or trust-chain verification.
- Centralized organization governance.
- Hosted skill services.
- Automatic execution from skill content.
- Skills granting or changing tool permissions.
- Skills approving actions.
- Skills altering provider profiles.
- Skills altering policy profiles or sensitivity classes.
- Skills writing files.
- Skills replacing templates.
- Skills replacing task specs.
- Skills replacing policy.
- Optional `skill create`.
- Optional `skill export`.
- Changing existing run behavior for tasks that do not request or receive skill
  guidance.

## Further Notes

The highest-risk parts of v1.5.0 are authority confusion, context provenance, hash
stability, local skill validation, duplicate handling, and documentation claim
drift. The first implementation phases should prove a skill can be listed,
validated, resolved, included, rejected, and audited without crossing the policy
boundary.

The central product distinction is that templates answer what files and
configuration should be generated, while skills answer what workflow procedure
should be followed. That distinction should remain visible in CLI copy, docs,
schemas, and tests.

The TDD workflow applies to v1.5.0 implementation itself: each phase should be
implemented one observable behavior at a time, with refactoring only after the
relevant behavior is green.
