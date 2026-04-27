# PRD: Agent Harness V4 Provider Core

## Problem Statement

Agent Harness v1.0.0 proves a controlled local CLI/runtime baseline with
policy-gated context, approvals, provider-input evidence, recorded provider
fixtures, release evidence, and audit artifacts. It still cannot prove that a
configured live model provider can safely participate in a controlled run.

The current provider path is useful for demos and deterministic tests, but it
does not yet establish a strict structured-output boundary between untrusted
model responses and runtime action planning. A malformed, unsafe, or unsupported
provider response must fail before it can influence tool execution. Reviewers
also need provider-call evidence that ties provider input, approvals,
checkpoints, redacted artifacts, and validated action envelopes together.

Without V4 Provider Core, the project remains a strong control-plane
demonstration rather than a policy-safe provider runtime.

## Solution

V4 introduces a provider-core release boundary. Provider output is treated as
untrusted data and parsed into a strict `provider_action_envelope.v1` before any
runtime action planning. Mock, recorded-fixture, and opt-in live
OpenAI-compatible paths use the same validation boundary.

OpenAI-compatible live execution is supported only as an explicit smoke path. It
requires environment opt-in, a configured provider profile, network/trust-zone
policy allowance, provider-use approval, and public or synthetic prompts. Normal
CI remains credential-free and deterministic through mocks and recorded
fixtures.

Provider-call artifacts become inspectable evidence rather than raw provider
payload storage. They bind provider mode, profile, trust zone, approvals,
provider-input hash, action-envelope hash, checkpoint hash, latency, token
metrics when available, and redacted prompt/response artifact references.

The solution deliberately avoids fixture capture tooling, retention profiles,
API/UI work, MCP, multi-agent orchestration, retrieval redesign, production
deployment, and enterprise or compliance claims.

## User Stories

1. As a user, I want a configured provider to participate in a controlled Agent
   Harness run, so that the harness proves real provider integration.
2. As a reviewer, I want provider-call evidence with approval, checkpoint,
   provider-input, action-envelope, and redaction links, so that I can audit the
   run.
3. As a security-minded maintainer, I want malformed or unsafe provider output
   rejected before tool execution, so that providers cannot bypass policy.
4. As a contributor, I want provider tests to run with mocks and recorded
   fixtures in normal CI, so that tests remain deterministic and
   credential-free.
5. As an operator, I want live provider smoke tests to skip when credentials or
   explicit opt-in are missing, so that optional validation never breaks routine
   CI.

## Behavioral Requirements

1. Provider output is parsed into `provider_action_envelope.v1` before runtime
   action planning.
2. Invalid JSON, malformed envelopes, unknown tool names, invalid arguments,
   refusals, and unsupported actions fail clearly before tool execution.
3. Mock and recorded-fixture provider paths use the same envelope validation as
   live provider paths.
4. Provider adapters return validated envelopes and cannot call tools directly.
5. Provider profiles are validated before provider use with actionable
   diagnostics that mention env var names but never env var values.
6. Live OpenAI-compatible execution requires explicit env opt-in, a configured
   profile, network/trust-zone policy allowance, and provider-use approval.
7. Provider input is derived only from the context manifest and preserves
   hard-deny behavior for `secret`, `credential`, `pii`, and `customer`.
8. Provider-call artifacts record mode, provider profile, trust zone, approval
   ids, provider-input hash, action-envelope hash, checkpoint hash, latency,
   token metrics when available, and redacted artifact references.
9. Redacted prompt artifacts contain only allowed or redacted provider-input
   records.
10. Redacted response artifacts contain a validated envelope or sanitized error
    evidence.
11. Raw credentials, private data, hard-denied data, and sensitive payloads are
    not stored in provider artifacts.
12. Normal CI uses mocks and existing recorded fixtures only; credentials and
    live provider calls are not required.
13. Live provider smoke tests are opt-in and skip, not fail, when credentials or
    live opt-in are absent.
14. Docs explain provider setup, safety boundaries, recorded-fixture
    expectations, live-smoke behavior, and unsupported roadmap items.

## Implementation Decisions

- Preserve the existing public CLI surface: `run`, `approve`, `inspect run`,
  `eval`, and `docs check`.
- Add `provider_action_envelope.v1` as the provider-output boundary before
  runtime action planning.
- Keep provider adapters behind a contract that returns validated envelopes and
  provider-call evidence, not direct tool execution.
- Use OpenAI-compatible live smoke as the only V4 live provider path.
- Keep Anthropic live support, MCP, API/UI, retention profiles, fixture capture,
  and fixture replay commands out of V4.
- Use the existing recorded-fixture mechanism for normal provider tests.
- Require recorded fixtures to use public or synthetic prompts only and contain
  no secrets, raw credentials, private data, or sensitive payloads.
- Add or extend provider artifact schemas rather than storing raw provider
  request or response bodies.
- Keep existing provider approval and provider-input policies as the permission
  ceiling.
- Treat provider profile validation as a pre-provider-use gate, not as a new
  command surface.

## Testing Decisions

- Start each plan phase with one failing public-interface test, then implement
  the minimum code needed to turn it green.
- Test the provider envelope boundary through runtime or provider-gateway public
  behavior, not private parsing helpers.
- Add adversarial tests for invalid JSON, malformed envelopes, unknown tools,
  invalid arguments, refusals, unauthorized actions, provider-input hard-deny
  leakage, and approval drift.
- Add deterministic integration coverage for mock and recorded-fixture provider
  paths using the same validation contract.
- Add optional live-smoke coverage that skips unless explicit opt-in and
  credentials exist.
- Extend evals to prove provider-core behavior through deterministic paths,
  including recorded fixture execution, provider evidence, redacted artifacts,
  and malformed-output rejection.
- Docs checks must keep implemented behavior separate from roadmap claims.

## Out of Scope

- Fixture capture tooling or new fixture capture/replay CLI commands.
- Retention profile system.
- API, web UI, approval UI, or hosted service work.
- MCP resources, prompts, or tool execution.
- Multi-agent workflows.
- Retrieval redesign, production Qdrant server mode, or remote embeddings.
- Anthropic live provider support.
- Production deployment hardening.
- Enterprise readiness, compliance readiness, or attestation claims.
- Broad model-quality benchmark expansion beyond provider-core evals.

## Further Notes

- V4 should be implemented as a controlled extension of the v1.0.0 public
  contract, not as a new product surface.
- The highest-risk boundary is allowing untrusted model output to influence tool
  execution. The envelope validator and policy re-check must remain central to
  the design.
- Live smoke should prove integration only with public or synthetic inputs. It
  is not a general live-provider certification.
- Redacted prompt and response artifacts should be inspectable enough for review
  while still excluding raw credentials and sensitive payloads.
