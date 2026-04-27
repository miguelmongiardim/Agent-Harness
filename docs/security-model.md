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
enterprise DLP, fixture capture tooling, API/UI surfaces, MCP support,
multi-agent execution, retention profiles, retrieval redesign, Anthropic live
support, compliance readiness, enterprise claims, and multi-tenant guarantees.
Those belong in future roadmap work.
