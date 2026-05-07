# agent_harness.security

## Purpose

`agent_harness.security` owns local security scanning and advisory collection for
tasks and artifacts. It detects high-risk task content, unsafe patterns, and
available advisory reports so runtime, governance, and release evidence can
surface security-relevant findings.

The package provides local checks over configured inputs and artifacts. It is
not a vulnerability database client, dependency updater, or external scanner.

## Key Files

| File | Role |
| --- | --- |
| `schema.py` | Security finding, gate decision, and findings report schemas. |
| `scanner.py` | Scans task content and related text for risky instructions, secrets-like patterns, dangerous commands, and policy-relevant security findings. |
| `advisory.py` | Collects existing advisory report artifacts from the workspace when present. |
| `__init__.py` | Lazily exports `scan_task_security` and `collect_advisory_reports`. |

## Boundaries

Security scanning reports findings; policy and runtime decide how those findings
affect execution. Do not hide findings or silently downgrade scanner errors when
they affect run or governance evidence.
