# Security Model

Agent Harness is enterprise-inspired, not enterprise-ready.

The security model is built around explicit policy mediation:

- Every context source, retrieval result, tool call, approval, export, and
  runtime decision must pass through the policy engine.
- Policy profiles are permission ceilings. Task specs can narrow allowed tools,
  paths, and commands, but cannot grant capabilities absent from the profile.
- All external or model-produced data is untrusted evidence. It may inform a
  decision, but it does not authorize a decision.
- Write operations require approval records that bind the run id, action id,
  tool name, arguments hash, policy profile, checkpoint hash, and proposed
  effect hash.
- Policy is re-checked immediately before an approved action executes.

The current implementation intentionally excludes production identity, remote
provider controls, centralized secrets management, hardened sandbox isolation,
enterprise DLP, and multi-tenant guarantees. Those belong in future roadmap work.
