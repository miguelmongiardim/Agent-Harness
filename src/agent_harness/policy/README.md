# agent_harness.policy

## Purpose

`agent_harness.policy` owns policy loading and all shared authorization
decisions. It mediates read/write roots, denied globs, sensitivity classes,
redaction, provider-use approvals, generated context, skill context, template
writes, tool calls, test command allowlists, and git commit boundaries.

Policy is the common gate for runtime, context, tools, templates, provider
input, skills, and orchestration. Other packages may provide domain data, but
policy decides whether that data or operation is allowed.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | `policy.v2` profile, provider input rules, trust policy, approval policy, scanner policy, template capability policy, orchestration policy, and policy decision schemas. |
| `engine.py` | Loads policy profiles and implements `PolicyEngine` decisions for paths, context, tools, templates, providers, commits, and redaction. |
| `approvals.py` | Builds provider-use approval records and approval binding data. |
| `classifiers.py` | Classifies paths into sensitivity categories based on policy rules. |
| `path_sandbox.py` | Resolves relative paths, matches denied globs, and checks roots. |
| `redaction.py` | Compiles redaction patterns and redacts text while reporting matched patterns. |
| `__init__.py` | Lazily exports policy loading and engine classes. |

## Decision Model

Most decisions return a `PolicyDecision` with an ID, allowed status, approval
requirement, reason, and matched rules. Runtime and tool code records those
decisions as evidence so approval bindings can later prove they apply to the
same action, checkpoint, policy profile, and proposed effect.

## Boundaries

Policy should stay deterministic and local. It should not execute tools, read
provider responses, render templates, build context manifests, or write run
summaries. It provides decisions that those packages must honor.
