# agent_harness.provider_fixtures

## Purpose

`agent_harness.provider_fixtures` stores recorded provider response fixtures for
tests, demos, and deterministic provider-gateway validation. These JSON files
let the repository exercise provider envelope handling without requiring live
network calls or real credentials.

This directory is package data, not provider transport code. Provider schemas,
profile validation, and envelope parsing live in `agent_harness.model`.

## Contents

| Directory | Role |
| --- | --- |
| `openai_compatible/` | Recorded OpenAI-compatible response envelopes for read-only, refusal, unsupported, invalid-envelope, and invalid-argument scenarios. |
| `anthropic/` | Recorded Anthropic-style fixture data used by provider compatibility tests. |

## Boundaries

Fixtures must not contain secrets, real provider request payloads, private user
data, or live responses that cannot be safely committed. Add new fixtures only
when they exercise a stable provider-envelope behavior that tests or demos need.
