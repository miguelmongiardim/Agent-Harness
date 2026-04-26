# Provider Audit Demo

This demo uses a recorded OpenAI-compatible provider fixture with a
non-mock local endpoint trust zone, `network: false`, and required provider-use
approval.

Run the stable golden path from the repo root:

```bash
agent-harness demo provider-audit
```

The command prints JSON with the inspectable `run_id` and writes
`.agent-harness/release/evidence/demo-provider-audit.json` for release
readiness. Inspect the returned run from the printed `inspect.cwd`, normally:

```bash
cd examples/provider_audit
agent-harness inspect run <run-id>
```

To exercise the manual pause/resume approval path, run it from this directory:

```bash
set AGENT_HARNESS_FIXED_RUN_ID=provider-audit-demo-run
set AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT=recorded://openai_compatible/read_only
agent-harness run task.json
agent-harness approve provider-audit-demo-run <approval-id> --decision approve
agent-harness inspect run provider-audit-demo-run
agent-harness export json provider-audit-demo-run
agent-harness export markdown provider-audit-demo-run
agent-harness export sarif provider-audit-demo-run
```
