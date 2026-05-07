# agent_harness.config

## Purpose

`agent_harness.config` owns local configuration loading and public model
serialization. It is the boundary that reads `agent-harness.yaml`, normalizes
supported public schema versions, and turns JSON/YAML files into typed Pydantic
models used by the rest of the harness.

The package intentionally implements only a small YAML subset for local config
files. It supports mappings, simple nested mappings/lists, strings, integers,
booleans, and JSON-style inline lists. More complex parsing should be added only
if the public config contract needs it.

## Key Files

| File | Role |
| --- | --- |
| `__init__.py` | Provides `DEFAULT_CONFIG`, minimal YAML parsing, config loading, schema-version normalization, model loading, and model dumping helpers. |
| `schema.py` | Defines `config.v2` Pydantic contracts for harness config, retrieval config, local Qdrant settings, template directories, and skill directories. |

## Public Behavior

`load_config(root)` reads `agent-harness.yaml` when it exists and otherwise
returns `DEFAULT_CONFIG`. `load_config_with_schema_evidence(root)` also returns
the original and effective schema versions so run artifacts can record
compatibility evidence.

`load_public_model()` and `load_public_model_with_schema_evidence()` are shared
helpers for public artifacts such as task, policy, config, and template-related
models. The effective schema map currently preserves compatibility for
`config.v1`, `task.v1`, and `policy.v1` by normalizing them to their v2
contracts.

## Boundaries

Config code validates shape and compatibility. It does not decide whether a
path, provider, tool, template, or context item is allowed; those decisions
belong to `policy` and the package that owns the behavior being configured.
