from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.storage import RunStore
from agent_harness.utils import write_json


def export_json(store: RunStore, output: Path) -> Path:
    write_json(
        output,
        {
            "schema_version": "run_export.v1",
            "run_id": store.run_id,
            "summary": store.read_data("summary.json"),
            "artifact_index": store.read_data("artifact-index.json"),
            "events": store.events(),
        },
    )
    return output


def export_markdown(store: RunStore, output: Path) -> Path:
    summary = store.read_data("summary.json")
    artifact_index = store.read_data("artifact-index.json")
    events = store.events()
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


def export_sarif(store: RunStore, output: Path) -> Path:
    results: list[dict[str, Any]] = []
    for event in store.events():
        if event.get("type") != "policy_decision":
            continue
        decision = event.get("payload", {}).get("decision", {})
        level = "note" if decision.get("allowed") else "error"
        if decision.get("approval_required"):
            level = "warning"
        results.append(
            {
                "ruleId": "AGENT-HARNESS-POLICY",
                "level": level,
                "message": {"text": str(decision.get("reason", "policy decision"))},
                "properties": {
                    "decision_id": decision.get("decision_id"),
                    "matched_rules": decision.get("matched_rules", []),
                },
            }
        )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agent-harness",
                        "informationUri": "https://github.com/",
                        "rules": [
                            {
                                "id": "AGENT-HARNESS-POLICY",
                                "name": "Policy decision",
                                "shortDescription": {
                                    "text": "Agent Harness policy decision evidence"
                                },
                            }
                        ],
                    }
                },
                "results": results,
            }
        ],
    }
    write_json(output, sarif)
    return output
