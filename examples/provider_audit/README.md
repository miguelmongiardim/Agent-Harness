# Provider Audit Demo

This demo uses a recorded OpenAI-compatible provider fixture with a
non-mock local endpoint trust zone, `network: false`, and required provider-use
approval.

Run it from this directory:

```bash
set AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT=recorded://openai_compatible/read_only
agent-harness run task.json
agent-harness approve provider-audit-demo-run <approval-id> --decision approve
agent-harness inspect run provider-audit-demo-run
agent-harness export json provider-audit-demo-run
agent-harness export markdown provider-audit-demo-run
agent-harness export sarif provider-audit-demo-run
```
