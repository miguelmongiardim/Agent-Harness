# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using V2 config, task, policy, and template inputs; a deterministic mock agent;
configured provider profiles; provider-input policy gates; strict provider
action envelopes; opt-in OpenAI-compatible live smoke; redacted provider-call
evidence; local lexical and local dense fixture retrieval evidence;
approval-bound template application; separate `git_commit` approval; packaged
benchmark adapters; provider audit demos; release-readiness reports; audit
logs; evals; an optional LangGraph boundary proof; and reproducible artifacts.

## v1.0.0 Status

v1.0.0 closes the V3 release-maturity track. The stable local OSS scope covers
core CLI behavior, public schema compatibility policy, package and
clean-install evidence, reproducible demos, Docker demo packaging, pre-commit
and CI hygiene, bundled template validation, and release-readiness evidence.

The detailed V3 plan lives in [plans/agent-harness-v3.md](../plans/agent-harness-v3.md).

The current conception alignment review lives in
[docs/conception-alignment.md](conception-alignment.md). It compares the
original `deep-research-report.md` vision with the v1.0.0 implementation and
defines the remaining drift.

## v1.1.0 Status

v1.1.0 closes the V4 Provider Core track:
[docs/prd-agent-harness-v4.md](prd-agent-harness-v4.md) and
[plans/agent-harness-v4.md](../plans/agent-harness-v4.md). It adds strict
provider action envelopes, profile validation, opt-in OpenAI-compatible live
smoke, provider-call evidence, redacted prompt/response artifacts,
provider-core evals, and setup/safety docs.

V4 does not promote fixture capture tooling, retention profiles, web UI, MCP
execution, multi-agent orchestration, production Qdrant server mode, Anthropic
live support, or enterprise readiness.

## v1.2.0 V5 Direction

V5 is planned as local-first retrieval hardening:
[docs/prd-agent-harness-v5.md](prd-agent-harness-v5.md) and
[plans/agent-harness-v5.md](../plans/agent-harness-v5.md). The track keeps
base-install lexical retrieval available while adding local index lifecycle
commands, deterministic dense test embeddings, local-only FastEmbed behavior,
persistent local Qdrant storage, loopback-only Qdrant server developer support,
hybrid retrieval, scorecards, a local retrieval quality demo, and
policy-filtered context manifest evidence.

Cloud Qdrant, hosted embedding providers, remote embeddings, remote embedding
APIs, remote vector databases, API-key-backed Qdrant endpoints, HTTPS remote
Qdrant endpoints, production Qdrant server operation, MCP, API/UI surfaces,
multi-agent workflows, enterprise retrieval claims, and compliance-ready
retrieval claims remain future-only and are not V5 behavior.

## Release Maintenance Priorities

- Preserve the v1.0.0 compatibility and deprecation contract.
- Keep release readiness as the control surface for package, docs, demos,
  templates, changelog, CI, and release artifacts.
- Maintain local and Docker provider-audit golden paths.
- Keep every bundled template validated and allow clean empty-destination scaffolding
  without weakening overwrite protections.
- Keep pre-commit and CI gates stable for routine changes.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add external template catalogs and remote template discovery.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
- Add cloud or production Qdrant modes and deployment-scale retrieval tuning.
- Add hosted or remote retrieval providers.
- Add MCP resources, prompts, or tool execution behind explicit policy
  boundaries.
- Add enterprise/compliance readiness work, including production identity,
  centralized secrets management, hardened sandboxing, and attestation.
