from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.storage import RunStore
from agent_harness.utils import write_json


def export_sarif(store: RunStore, output: Path) -> Path:
    results: list[dict[str, Any]] = []
    rules: dict[str, dict[str, Any]] = {
        "AGENT-HARNESS-POLICY": {
            "id": "AGENT-HARNESS-POLICY",
            "name": "Policy decision",
            "shortDescription": {
                "text": "Agent Harness policy decision evidence",
            },
        }
    }
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
    security_path = store.run_dir / "security_findings.json"
    if security_path.exists():
        report = store.read_data("security_findings.json")
        gate = report.get("gate", {})
        for finding in report.get("findings", []):
            if not isinstance(finding, dict):
                continue
            rule_id = str(finding.get("rule_id", "AGENT-HARNESS-SECURITY"))
            rules.setdefault(
                rule_id,
                {
                    "id": rule_id,
                    "name": rule_id,
                    "shortDescription": {"text": "Agent Harness security finding"},
                },
            )
            result: dict[str, Any] = {
                "ruleId": rule_id,
                "level": _level_for_security_severity(str(finding.get("severity", "info"))),
                "message": {"text": str(finding.get("message", "security finding"))},
                "properties": {
                    "finding_id": finding.get("finding_id"),
                    "severity": finding.get("severity"),
                    "scanner": finding.get("scanner"),
                    "gate_status": gate.get("status"),
                    "gate_blocking": finding.get("finding_id")
                    in gate.get("blocking_finding_ids", []),
                },
            }
            path = finding.get("path")
            line = finding.get("line")
            if isinstance(path, str):
                location: dict[str, Any] = {
                    "physicalLocation": {
                        "artifactLocation": {"uri": path},
                    }
                }
                if isinstance(line, int):
                    location["physicalLocation"]["region"] = {"startLine": line}
                result["locations"] = [location]
            results.append(result)
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agent-harness",
                        "informationUri": "https://github.com/",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    write_json(output, sarif)
    return output


def _level_for_security_severity(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "error"
    if severity == "medium":
        return "warning"
    return "note"
