# v1.7.0 Orchestration Workflow

This example is the v1.7.0 local orchestration golden path. It runs a sequential
planner, implementer, reviewer, and tester workflow over a small Python fixture
without external services.

Run the workflow commands from this directory, then return to the repo root for
release readiness:

```powershell
uv run agent-harness orchestration run orchestration.json --dry-run
uv run agent-harness orchestration inspect workflow-demo
uv run agent-harness orchestration export workflow-demo
uv run agent-harness mcp resources list --json
uv run agent-harness mcp resources read agent-harness://orchestrations/workflow-demo/summary --json
uv run agent-harness mcp resources read agent-harness://orchestrations/workflow-demo/handoffs --json
cd ..\..
uv run agent-harness release readiness --version 1.9.0
```

The workflow records normal child `task.v2` run artifacts, aggregate
orchestration summary, events, manifest, generated dependency handoffs, export
evidence, and metadata-only MCP access logs.

Parallel execution, nested orchestration, MCP execution, hosted APIs, operator
UI support, and enterprise governance remain future scope.
