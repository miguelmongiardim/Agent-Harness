from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.storage import RunStore
from agent_harness.utils import write_json


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
