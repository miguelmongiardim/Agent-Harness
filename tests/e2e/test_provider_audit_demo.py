from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_provider_audit_demo_command_returns_inspectable_run_id() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-27T10:00:00Z"
    env.pop("AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT", None)

    demo = _run_cli(repo_root, env, "demo", "provider-audit")
    payload = json.loads(demo.stdout)

    run_id = payload["run_id"]
    workspace = repo_root / payload["workspace"]
    assert payload["schema_version"] == "demo_run.v1"
    assert payload["demo_id"] == "provider-audit"
    assert payload["status"] == "completed"
    assert payload["inspect"]["cwd"] == "examples/provider_audit"
    assert payload["inspect"]["command"] == f"agent-harness inspect run {run_id}"

    inspected = json.loads(_run_cli(workspace, env, "inspect", "run", run_id).stdout)
    assert inspected["summary"]["run_id"] == run_id
    assert inspected["summary"]["status"] == "completed"
    assert inspected["provider_calls"]["calls"]
    assert inspected["provider_input"]["records"]

    evidence_path = (
        repo_root / ".agent-harness" / "release" / "evidence" / ("demo-provider-audit.json")
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert evidence["run_id"] == run_id
    assert evidence["command"] == "agent-harness demo provider-audit"


def test_provider_audit_demo_golden_path_is_covered_by_eval() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-27T10:05:00Z"
    env.pop("AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT", None)

    eval_run = _run_cli(repo_root, env, "eval")
    report = json.loads(Path(json.loads(eval_run.stdout)["report"]).read_text(encoding="utf-8"))
    results = {result["eval_id"]: result for result in report["results"]}

    provider_audit = results["provider-audit-demo-golden-path"]
    assert provider_audit["passed"] is True
    assert {
        "provider_input_created",
        "provider_call_recorded",
        "provider_use_approval_recorded",
    } <= {item["name"] for item in provider_audit["invariants"]}
    assert "summary" in provider_audit["artifacts"]
    assert "provider_calls" in provider_audit["artifacts"]


def test_python_refactor_secondary_demo_records_release_evidence() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-27T10:10:00Z"

    run = _run_cli(
        repo_root,
        env,
        "run",
        "examples/tasks/python_refactor.json",
        "--dry-run",
    )
    summary = json.loads(run.stdout)
    inspect = json.loads(_run_cli(repo_root, env, "inspect", "run", summary["run_id"]).stdout)

    evidence_path = (
        repo_root / ".agent-harness" / "release" / "evidence" / ("demo-python-refactor.json")
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert inspect["summary"]["status"] == "dry_run"
    assert evidence["status"] == "passed"
    assert evidence["run_id"] == summary["run_id"]
    assert evidence["command"] == (
        "agent-harness run examples/tasks/python_refactor.json --dry-run"
    )


def test_provider_audit_demo_pauses_resumes_and_exports_all_evidence(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "provider_audit"
    shutil.copytree(repo_root / "examples" / "provider_audit", workspace)
    env = os.environ.copy()
    env["AGENT_HARNESS_FIXED_RUN_ID"] = "provider-audit-demo-run"
    env["AGENT_HARNESS_FIXED_TIME"] = "2026-04-26T19:00:00Z"
    env["AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT"] = "recorded://openai_compatible/read_only"

    run = _run_cli(workspace, env, "run", "task.json")
    summary = json.loads(run.stdout)

    assert summary["status"] == "paused"
    assert len(summary["approvals"]) == 1
    approval_action_id = summary["approvals"][0]

    pending = _inspect(workspace, env)
    provider = pending["provider"]
    approval = _approval_record(pending)

    assert provider["transport"] == "openai_compatible"
    assert provider["trust_zone"] == "local_endpoint"
    assert provider["network"] is False
    assert provider["requires_approval"] is True
    assert approval["tool_name"] == "provider_use"
    assert approval["status"] == "pending"
    assert approval["provider_use_binding"]["provider_profile_id"] == "provider-audit"
    assert pending["provider_input"]["records"][0]["policy_action"] == "allow"
    assert not any(event["type"] == "model_action" for event in pending["events"])

    _run_cli(
        workspace,
        env,
        "approve",
        "provider-audit-demo-run",
        approval_action_id,
        "--decision",
        "approve",
        "--actor",
        "reviewer",
    )

    inspected = _inspect(workspace, env)
    provider_calls = inspected["provider_calls"]["calls"]

    assert inspected["summary"]["status"] == "completed"
    assert provider_calls
    assert provider_calls[0]["approval_ids"] == [approval_action_id]
    assert provider_calls[0]["mode"] == "recorded_fixture"
    assert provider_calls[0]["redacted_prompt_summary"]["included_records"] == 1
    assert provider_calls[0]["redacted_response_summary"]["kind"] == "tool_calls"
    assert "safe to include" not in json.dumps(inspected["provider_calls"])
    assert "docs/public.md" in {record["path"] for record in inspected["provider_input"]["records"]}
    assert any(event["type"] == "provider_call_recorded" for event in inspected["events"])

    json_export = workspace / "exports" / "provider-audit.json"
    md_export = workspace / "exports" / "provider-audit.md"
    sarif_export = workspace / "exports" / "provider-audit.sarif"

    _run_cli(
        workspace,
        env,
        "export",
        "json",
        "provider-audit-demo-run",
        "--output",
        str(json_export),
    )
    _run_cli(
        workspace,
        env,
        "export",
        "markdown",
        "provider-audit-demo-run",
        "--output",
        str(md_export),
    )
    _run_cli(
        workspace,
        env,
        "export",
        "sarif",
        "provider-audit-demo-run",
        "--output",
        str(sarif_export),
    )

    exported = json.loads(json_export.read_text(encoding="utf-8"))
    sarif = json.loads(sarif_export.read_text(encoding="utf-8"))

    assert exported["run_id"] == "provider-audit-demo-run"
    assert exported["summary"]["status"] == "completed"
    assert "Provider Audit Demo" in md_export.read_text(encoding="utf-8")
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"]


def _run_cli(cwd: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "agent_harness", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def _inspect(cwd: Path, env: dict[str, str]) -> dict[str, object]:
    inspect = _run_cli(cwd, env, "inspect", "run", "provider-audit-demo-run")
    return json.loads(inspect.stdout)


def _approval_record(inspected: dict[str, object]) -> dict[str, object]:
    events = inspected["events"]
    assert isinstance(events, list)
    for event in events:
        if (
            isinstance(event, dict)
            and event.get("type") == "approval_recorded"
            and event.get("payload", {}).get("operation") == "provider_use"
        ):
            approval = event["payload"]["approval"]
            assert isinstance(approval, dict)
            return approval
    raise AssertionError("provider-use approval was not recorded")
