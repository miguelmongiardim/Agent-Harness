# agent_harness.model.adapters

## Purpose

`agent_harness.model.adapters` owns provider transport adapter integration. It
is the place where provider-specific request/response envelopes are validated
and converted into the deterministic action format expected by the runtime.

The current public adapter export is `ProviderGateway`, with
`ProviderEnvelopeValidationError` for invalid recorded or live-style provider
envelopes.

## Key Files

| File | Role |
| --- | --- |
| `provider_gateway.py` | Validates provider response envelopes, handles supported tool-call output shapes, rejects malformed or unsupported envelopes, and returns runtime-ready tool calls. |
| `__init__.py` | Exports the provider gateway and validation error. |

## Boundaries

Adapters should not bypass provider profile checks, provider-use approvals, or
provider-input redaction. They receive already-authorized input from the runtime
and return validated action data. Optional live transports should fail clearly
when unavailable or unsupported.
