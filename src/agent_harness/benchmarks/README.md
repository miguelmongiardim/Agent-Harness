# agent_harness.benchmarks

## Purpose

`agent_harness.benchmarks` owns local benchmark execution and comparison
evidence. It turns packaged benchmark case records into isolated local
workspaces, runs the harness against those workspaces, and writes evidence that
points back to real run artifacts instead of inventing a separate benchmark-only
result format.

The package is deliberately local and deterministic. It is not a live benchmark
service, remote leaderboard client, or external dataset downloader.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Public benchmark schemas such as benchmark packs, cases, adapter evidence, case results, comparison modes, metrics, recommendations, and suite results. |
| `packs.py` | Lists packaged benchmark packs, loads pack records, stages case workspaces, runs benchmark cases, approves pending patch actions for benchmark flows, and records retrieval evidence links. |
| `adapters.py` | Defines the adapter protocol and the local sample adapter that writes case files, tasks, tests, docs, and policy/config artifacts into a benchmark workspace. |
| `comparison.py` | Runs a baseline mode first, runs deterministic generated orchestration modes when eligible, gathers child run evidence, computes comparison metrics, and writes comparison artifacts. |
| `interpretation.py` | Produces deterministic role recommendations and reason codes from comparison metrics without mutating policy or orchestration specs. |
| `__init__.py` | Lazily exports the public benchmark functions used by the CLI and evals. |

## Execution Flow

1. `list_benchmark_packs()` and `load_benchmark_pack()` read packaged benchmark
   metadata from `agent_harness.bundled_benchmarks`.
2. `run_benchmark_case()` selects a case, stages an isolated workspace, writes
   the local task/config/policy files, and delegates execution to
   `HarnessRuntime`.
3. `run_benchmark_comparison()` stages separate workspaces for baseline and
   orchestration modes, then records mode status, child artifacts, handoff
   usefulness, policy violations, approval correctness, test results, and
   failure attribution.
4. `run_benchmark_comparison_suite()` aggregates per-case comparison artifacts
   while preserving skips and failures as inspectable case-level records.

## Boundaries

Benchmark code may coordinate runtime, storage, orchestration, and exporters,
but it should not become the runtime or policy engine. It should keep evidence
as project-relative references to run artifacts, event logs, approvals, exports,
and orchestration summaries.

New benchmark data belongs in `bundled_benchmarks` or in a configured local pack
format, not in the execution code. New metrics should be deterministic and
traceable to stored evidence.
