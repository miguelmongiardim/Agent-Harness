# agent_harness.bundled_templates

## Purpose

`agent_harness.bundled_templates` stores template package data that ships with
Agent Harness. It contains registry metadata, legacy JSON template records,
`template.v2.toml` pack manifests, and scaffold files copied or rendered by the
`agent_harness.templates` package.

This directory is data, not the template engine. Loading, validation,
substitution, apply planning, policy checks, and apply evidence belong in
`agent_harness.templates`.

## Contents

| Item | Role |
| --- | --- |
| `registry.sqlite3` | Bundled registry used by `templates.registry` to list known templates. |
| `*.json` | Legacy template registry records kept for compatibility tests and packaged catalog behavior. |
| `cli-tool/` | Local CLI project scaffold pack. |
| `fastapi-service/` | Local FastAPI service scaffold pack. |
| `provider-audit/` | Provider-audit workflow scaffold pack. |
| `python-lib/` | Python library scaffold pack. |
| `retrieval-quality/` | Retrieval-quality workflow scaffold pack with example docs and eval/config/task files. |

## Template Pack Shape

A bundled template pack is expected to keep its manifest at
`<template-id>/template.v2.toml`. Rendered files live under
`<template-id>/files/`. Existing `files/README.md` documents the generated
project that the template creates; this README documents the source data
directory itself.

## Boundaries

Keep bundled template data deterministic and portable. Do not include secrets,
machine-local paths, live provider payloads, or remote-only assumptions. New
capabilities in a template manifest must be reflected in template schema and
validation behavior before the pack depends on them.
