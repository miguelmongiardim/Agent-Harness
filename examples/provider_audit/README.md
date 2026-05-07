# Provider Audit Demo

This demo uses a recorded OpenAI-compatible provider fixture with a
non-mock local endpoint trust zone, `network: false`, and required provider-use
approval.

Run the stable golden path from the repo root:

```powershell
uv run agent-harness demo provider-audit
```

The command prints JSON with the inspectable `run_id` and writes
`.agent-harness/release/evidence/demo-provider-audit.json` for release
readiness. Inspect the returned run from the printed `inspect.cwd`, normally:

```powershell
cd examples\provider_audit
uv run agent-harness inspect run <run-id>
```

To exercise the manual pause/resume approval path, run it from this directory:

```powershell
$env:AGENT_HARNESS_FIXED_RUN_ID = "provider-audit-demo-run"
$env:AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT = "recorded://openai_compatible/read_only"
uv run agent-harness run task.json
uv run agent-harness approve provider-audit-demo-run <approval-id> --decision approve
uv run agent-harness inspect run provider-audit-demo-run
uv run agent-harness export json provider-audit-demo-run
uv run agent-harness export markdown provider-audit-demo-run
uv run agent-harness export sarif provider-audit-demo-run
```
