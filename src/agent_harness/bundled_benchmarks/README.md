# agent_harness.bundled_benchmarks

## Purpose

`agent_harness.bundled_benchmarks` stores packaged benchmark data that ships with
the project. It is package data, not benchmark execution code. The runtime path
for these records lives in `agent_harness.benchmarks`.

The current bundled data includes `local-samples.json`, which defines local
sample cases used by benchmark commands, release evidence, and integration
tests.

## Data Contract

Bundled benchmark records are validated through `agent_harness.benchmarks.schema`
before they are executed. A case may describe files to stage, a task to run,
policy/config inputs, test commands, expected outputs, and adapter metadata.

Keep bundled benchmark data:

- deterministic and local-only
- free of secrets, credentials, private datasets, or machine-local paths
- small enough to run in the default local test profile unless explicitly marked
  as a slower or optional path elsewhere
- aligned with public benchmark schema versions

## Boundaries

Do not put execution helpers here. Add execution behavior in
`agent_harness.benchmarks`, and keep this package focused on portable records
that can be loaded through `importlib.resources`.
