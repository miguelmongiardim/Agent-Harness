# agent_harness.tools

## Purpose

`agent_harness.tools` owns typed tool execution and mutation planning. Runtime
turns model actions into `ToolCall` objects, policy evaluates those calls, and
`ToolExecutor` runs the allowed tools or returns pending approval observations
for approval-bound actions.

Tools are deliberately small and auditable. Each tool should have typed
arguments, deterministic observations, and clear policy mediation.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Tool spec, call, observation, and git commit plan schemas. |
| `registry.py` | Base tool argument model and tool-to-path-mode mapping. |
| `executor.py` | Evaluates calls through policy, dispatches tool implementations, handles dry-run behavior, and validates approval bindings. |
| `read_file.py` | Reads an allowed file through policy path checks. |
| `search_code.py` | Runs local code search with policy-aware path handling. |
| `patch_file.py` | Builds diffs, hashes proposed effects, and applies approved file patches. |
| `run_tests.py` | Executes allow-listed test commands and records observations. |
| `git_status.py` | Captures local git status as a read-only tool observation. |
| `git_commit.py` | Owns the separate approval-bound git commit plan, validation, execution, and committed-hash binding. |
| `shell_whitelist.py` | Checks whether test command arguments match the allowlist contract. |
| `__init__.py` | Lazily exports common tool argument classes and `ToolExecutor`. |

## Approval Flow

When a tool call requires approval, execution returns a `pending_approval`
observation with a proposed effect such as a redacted diff. Later execution must
validate that the approval record matches the run ID, action ID, tool name,
arguments hash, policy profile, checkpoint hash, and proposed effect hash.

## Boundaries

Tool implementations should not bypass policy, silently mutate files, or hide
command failures. Git commit behavior stays in `git_commit.py` because commit
approval has a different boundary from patch approval.
