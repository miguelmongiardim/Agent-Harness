# agent_harness.model

## Purpose

`agent_harness.model` owns model-client contracts, deterministic mock behavior,
provider profile validation, provider-use schemas, and provider adapter
integration points. It separates model/provider concerns from runtime
sequencing and policy enforcement.

The native runtime can use the deterministic mock model for local flows or a
provider profile when explicit provider-use policy and approval requirements are
satisfied.

## Key Files

| File | Role |
| --- | --- |
| `base.py` | Defines the model client protocol used by runtime code. |
| `mock.py` | Implements `DeterministicMockModel`, a content-driven local model used by demos, tests, evals, and deterministic dry runs. |
| `schema.py` | Provider profile, provider call audit, provider input manifest, provider approval binding, and run provider record schemas. |
| `profiles.py` | Validates provider profiles before use and reports profile configuration errors. |
| `openai_compatible.py` | Optional OpenAI-compatible adapter entry point that fails clearly when unsupported behavior or missing dependencies apply. |
| `adapters/` | Provider transport adapter boundary, currently including the provider gateway. |
| `__init__.py` | Lazily exports `DeterministicMockModel` and `ModelClient`. |

## Provider Flow

Provider-backed runs must pass through profile validation, provider-use policy,
approval binding, provider-input manifest construction, and provider gateway
envelope validation. Provider audit records and manifests are stored as run
evidence so downstream reports can inspect what happened without depending on
private runtime objects.

## Boundaries

Model code should not evaluate path permissions, execute tools, or write run
summaries directly. Runtime coordinates model calls, policy decides provider
authority and redaction, and storage records durable evidence.
