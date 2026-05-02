# Skills Workflow Demo

This demo exercises the v1.5.0 local skills workflow with the bundled
`prd-plan-tdd-workflow` skill. The task is intentionally small and local: it
asks Agent Harness to use workflow guidance while inspecting a feature brief.

Run the golden path from the repository root:

```powershell
uv sync
uv run agent-harness skill list
uv run agent-harness skill show prd-plan-tdd-workflow
uv run agent-harness skill validate prd-plan-tdd-workflow
uv run agent-harness skill resolve --task examples/skills_workflow/task.yaml
uv run agent-harness run examples/skills_workflow/task.yaml --dry-run
uv run agent-harness inspect run <run-id>
uv run agent-harness release readiness
```

Expected artifact examples live under `expected/`. They show the skill context
provenance and `skill_manifest.v1` evidence that release readiness verifies.
