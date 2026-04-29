# Security Model

Agent Harness is enterprise-inspired, not enterprise-ready.

The security model is built around explicit policy mediation:

- Every context source, retrieval result, tool call, approval, export, and
  runtime decision must pass through the policy engine.
- Policy profiles are permission ceilings. Task specs can narrow allowed tools,
  paths, and commands, but cannot grant capabilities absent from the profile.
- `policy.v2` is the current public policy contract. It has explicit sections
  for provider input, trust zones, approval requirements, scanner behavior,
  template capabilities, and migration policy.
- Provider-input policy defaults allow public input, allow generated input only
  as untrusted evidence, require approval for internal input, deny confidential,
  restricted, and unknown input, and hard-deny secret, credential, pii, and
  customer input.
- All external or model-produced data is untrusted evidence. It may inform a
  decision, but it does not authorize a decision.
- V8 skills are workflow guidance only. Skill content cannot grant tools, widen
  policy, approve actions, alter provider profiles, change sensitivity classes,
  execute code, mutate files, read environment variables, fetch network
  content, or bypass context policy. Current validation rejects
  authority-expanding skill content before it can be rendered as usable
  guidance, and current resolution records empty tool, approval, policy, and
  provider changes for task-requested and template-recommended skills. During
  runs, accepted skills enter `context_manifest.json` as policy-mediated
  evidence; rejected skill items record rejection reasons and hashes without
  body text. Provider input may include accepted skill guidance as context
  evidence, not as authority. Runs that pass security gates and use skills
  also emit `skill_manifest.json` after context assembly; runs blocked before
  context assembly do not claim skill inclusion.
- Provider-use approvals bind provider profile, trust zone, model id,
  provider-input hash, policy decision id, and checkpoint hash. Resume rejects
  drift in those bound fields before provider execution.
- Provider output is untrusted until it validates as
  `provider_action_envelope.v1`. Refusals, unsupported responses, malformed
  JSON, unknown tool names, and invalid tool arguments fail before runtime tool
  execution.
- Provider-call artifacts record approval ids, provider-input hashes,
  action-envelope hashes, checkpoint hashes, redacted prompt/response artifact
  references, redacted summaries, latency/token metrics, and policy decision
  references. Raw provider request and response payloads are not stored by
  default.
- Recorded provider fixtures are the normal deterministic test path. Optional
  OpenAI-compatible live smoke requires explicit
  `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1`, a configured provider profile,
  endpoint/API-key environment variables, network/trust-zone policy allowance,
  and provider-use approval.
- Write operations require approval records that bind the run id, action id,
  tool name, arguments hash, policy profile, checkpoint hash, and proposed
  effect hash.
- `git_commit` is a separate high-risk approval from patch application. Commit
  approval binds the parent HEAD, exact file set, file content hashes, diff
  hash, final message hash, policy profile, and checkpoint hash, then stages
  only the approved files immediately before `git commit`.
- Policy is re-checked immediately before an approved action executes.
- First-party security findings can block runs before context or provider
  execution. External Gitleaks and CycloneDX reports are advisory when present;
  missing local tools are reported without failing normal local workflows.

The current implementation intentionally excludes production identity, remote
provider controls, centralized secrets management, hardened sandbox isolation,
enterprise DLP, fixture capture tooling, hosted API/UI surfaces, MCP support,
multi-agent execution, retention profiles, retrieval redesign, Anthropic live
support, compliance readiness, enterprise claims, and multi-tenant guarantees.
Those belong in future roadmap work.

The V9 MCP plan narrows future MCP scope to local stdio, read-only resources,
review prompts, policy-filtered evidence, and append-only MCP access evidence.
It keeps MCP tools, write-capable MCP, MCP approval actions, MCP run execution,
MCP provider execution, arbitrary filesystem resources, raw provider payload
resources, Streamable HTTP MCP, hosted MCP service, remote MCP gateways,
enterprise MCP registries, and MCP runtime adapter behavior out of V9.

V6 is a narrower local operator surface. Its security boundary is loopback-only
serving, token-protected local API routes, allowlisted run artifact access, and
approval decisions routed through the existing approval service. The current
slice implements the loopback serve command, `/health`, token enforcement for
`/api/v1/*`, run list/detail inspection over existing run artifacts, context
manifest inspection, policy inspection, and safe missing/malformed/denied
artifact status reporting. It also implements approval listing and approve/deny
API decisions through the existing approval service, preserving binding,
checkpoint, drift, policy re-check, approval artifact, and event behavior. It
serves a packaged static UI from local package assets with no external CDN,
remote font, analytics, or external API calls; its approval controls call the
same local decision API and surface API errors without bypassing approval
binding. It must not claim hosted operation, enterprise authentication,
production web service readiness, or compliance readiness.
