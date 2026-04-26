from __future__ import annotations

from pathlib import Path

from agent_harness.storage import RunStore


def export_markdown(store: RunStore, output: Path) -> Path:
    summary = store.read_data("summary.json")
    artifact_index = store.read_data("artifact-index.json")
    events = store.events()
    task_title = _task_title(store)
    lines = [
        "# Agent Harness Run Export",
        "",
        f"- Run ID: {summary['run_id']}",
        f"- Task ID: {summary['task_id']}",
        f"- Status: {summary['status']}",
        f"- Events: {len(events)}",
        "",
        "## Artifacts",
    ]
    if task_title is not None:
        lines.insert(5, f"- Task Title: {task_title}")
    for name, path in sorted(artifact_index.get("artifacts", {}).items()):
        lines.append(f"- `{name}`: `{path}`")
    lines.extend(["", "## Policy Decisions"])
    for event in events:
        if event.get("type") != "policy_decision":
            continue
        payload = event.get("payload", {})
        decision = payload.get("decision", {})
        status = "ALLOW" if decision.get("allowed") else "DENY"
        if decision.get("approval_required"):
            status = "WARN"
        subject = payload.get("path") or payload.get("action_id") or "policy event"
        lines.append(f"- {status}: `{subject}` - {decision.get('reason', 'policy decision')}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def _task_title(store: RunStore) -> str | None:
    task_path = store.run_dir / "task.json"
    if not task_path.exists():
        return None
    task = store.read_data("task.json")
    title = task.get("title")
    return title if isinstance(title, str) and title else None
