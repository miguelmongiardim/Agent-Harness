# Provider Core

## Current Capabilities

Provider Core is the V4 boundary for controlled provider participation in Agent
Harness runs. Provider profiles are selected from `agent-harness.yaml`; tasks
or CLI flags can choose a configured profile but cannot define ad hoc provider
endpoints, models, transports, or trust zones.

Supported deterministic paths are:

- `mock` transport for local deterministic behavior.
- `openai_compatible` recorded fixtures using `recorded://openai_compatible/<fixture>`.

The only live path is a narrow OpenAI-compatible smoke path. It is disabled by
default and runs only when all of these are true:

- `AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS=1` is set.
- The configured endpoint and API-key environment variables are present.
- The provider profile uses a live endpoint, `network: true`, and
  `requires_approval: true`.
- Policy requires approval for the selected trust zone.
- The run receives provider-use approval or an explicit controlled
  auto-approval path is used for tests or demos.

Provider output must validate as `provider_action_envelope.v1` before runtime
action planning. The runtime writes provider-call evidence, redacted prompt
artifacts, and redacted response artifacts. Raw provider request bodies, raw
provider response bodies, credentials, hard-denied provider input, and sensitive
payloads are not stored.

Recorded fixtures must use public or synthetic inputs only. They are the normal
CI path and are expected to cover malformed output, invalid arguments, unknown
tools, refusals, unsupported responses, provider-input hard-deny behavior, and
approval drift.

## Roadmap

Out of scope for V4 Provider Core:

- Fixture capture tooling or fixture replay commands.
- API or web UI surfaces.
- MCP resources, prompts, or tool execution.
- Multi-agent workflows.
- Retention profiles.
- Retrieval redesign.
- Anthropic live provider support.
- Enterprise readiness, compliance readiness, attestation, or production
  deployment claims.
