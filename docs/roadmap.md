# Roadmap

## Current Capabilities

Agent Harness currently provides a controlled local software-engineering workflow
using V2 config, task, policy, and template inputs; a deterministic mock agent;
configured provider profiles; provider-input policy gates; local lexical and
local dense fixture retrieval evidence; approval-bound template application;
separate `git_commit` approval; packaged benchmark adapters; provider audit
demos; release-readiness reports; audit logs; evals; an optional LangGraph
boundary proof; and reproducible artifacts.

## V3 Direction

V3 is planned as the v1.0.0 release-maturity track. The scope is stable core
CLI behavior, public schema compatibility policy, package and clean-install
evidence, reproducible demos, Docker demo packaging, pre-commit and CI hygiene,
bundled template validation, and release-readiness evidence.

The detailed V3 plan lives in [plans/agent-harness-v3.md](../plans/agent-harness-v3.md).

## V3 Priorities

- Document and enforce the v1.0.0 compatibility and deprecation contract.
- Make release readiness the control surface for package, docs, demos,
  templates, changelog, CI, and release artifacts.
- Prove local and Docker provider-audit golden paths.
- Validate every bundled template and allow clean empty-destination scaffolding
  without weakening overwrite protections.
- Add pre-commit and CI gates that keep routine changes reviewable.

## Later Possibilities

- Add a web API.
- Add an approval and inspection UI.
- Add external template catalogs and remote template discovery.
- Expand optional LangGraph coverage beyond the current boundary proof.
- Add policy-mediated multi-agent support.
- Add pluggable DLP and redaction backends.
- Add OpenTelemetry dashboards.
- Add production Qdrant server mode and deployment-scale retrieval tuning.
- Add MCP resources, prompts, or tool execution behind explicit policy
  boundaries.
- Add enterprise/compliance readiness work, including production identity,
  centralized secrets management, hardened sandboxing, and attestation.
