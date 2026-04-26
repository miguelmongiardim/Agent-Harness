from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.runtimes.native import HarnessRuntime
from tests.conftest import seed_project


def test_high_security_finding_blocks_before_provider_execution(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    _seed_project_with_mock_provider(tmp_path)
    target = tmp_path / "dangerous.py"
    target.write_text(
        "import subprocess\n\nsubprocess.run(command, shell=True)\n",
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v2",
            "task_id": "high-security-block",
            "title": "Inspect dangerous file",
            "intent": "Inspect the target through a provider.",
            "provider_profile": "mock-default",
            "target_paths": ["dangerous.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-high-security-block")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:00:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "failed"
    assert "security_findings" in summary.artifacts
    findings = json.loads((tmp_path / summary.artifacts["security_findings"]).read_text())
    assert findings["gate"]["status"] == "failed"
    assert findings["gate"]["fail_threshold"] == "high"
    assert findings["findings"][0]["severity"] == "high"
    assert findings["findings"][0]["rule_id"] == "python-dangerous-shell"

    events = _read_jsonl(tmp_path / summary.artifacts["events"])
    event_types = [event["type"] for event in events]
    assert "security_scan_completed" in event_types
    assert "security_gate_blocked" in event_types
    assert "provider_selected" not in event_types
    assert "model_action" not in event_types


def test_high_security_finding_can_be_relaxed_to_report_only(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    relaxed = dict(DEFAULT_POLICY)
    relaxed["name"] = "relaxed-security"
    relaxed["security_fail_threshold"] = "critical"
    (tmp_path / "policies" / "relaxed-security.json").write_text(
        json.dumps(relaxed, indent=2), encoding="utf-8"
    )
    (tmp_path / "dangerous.py").write_text(
        "import subprocess\n\nsubprocess.run(command, shell=True)\n",
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v1",
            "task_id": "high-security-relaxed",
            "title": "Inspect dangerous file",
            "intent": "Inspect the target without changing files.",
            "policy_profile": "relaxed-security",
            "target_paths": ["dangerous.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-high-security-relaxed")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:05:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "completed"
    findings = json.loads((tmp_path / summary.artifacts["security_findings"]).read_text())
    assert findings["gate"]["status"] == "passed"
    assert findings["findings"][0]["severity"] == "high"


def test_critical_security_finding_blocks_even_when_high_is_relaxed(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    relaxed = dict(DEFAULT_POLICY)
    relaxed["name"] = "critical-only"
    relaxed["security_fail_threshold"] = "critical"
    (tmp_path / "policies" / "critical-only.json").write_text(
        json.dumps(relaxed, indent=2), encoding="utf-8"
    )
    (tmp_path / "credentials.py").write_text(
        'API_KEY = "not-a-real-key"\n',
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v1",
            "task_id": "critical-security-block",
            "title": "Inspect credentials",
            "intent": "Inspect the target without changing files.",
            "policy_profile": "critical-only",
            "target_paths": ["credentials.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-critical-security-block")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:10:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "failed"
    findings = json.loads((tmp_path / summary.artifacts["security_findings"]).read_text())
    assert findings["gate"]["status"] == "failed"
    assert findings["findings"][0]["severity"] == "critical"
    assert findings["findings"][0]["rule_id"] == "credential-literal"


def test_critical_secret_blocks_before_context_and_exports_policy_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project_with_mock_provider(tmp_path)
    (tmp_path / "credentials.py").write_text(
        'API_KEY = "not-a-real-key"\n',
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v2",
            "task_id": "critical-secret-policy-evidence",
            "title": "Inspect credentials",
            "intent": "Inspect the target through a provider.",
            "provider_profile": "mock-default",
            "target_paths": ["credentials.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-critical-secret-policy")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:18:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "failed"
    assert "security_findings" in summary.artifacts
    assert "context_manifest" not in summary.artifacts
    assert "provider" not in summary.artifacts
    run_dir = tmp_path / ".agent-harness" / "runs" / summary.run_id
    assert not (run_dir / "context_manifest.json").exists()
    assert not (run_dir / "provider.json").exists()

    findings = json.loads((tmp_path / summary.artifacts["security_findings"]).read_text())
    finding = findings["findings"][0]
    assert finding["severity"] == "critical"
    assert finding["source"] == "first_party_static"
    assert finding["location"] == {"path": "credentials.py", "line": 1}
    assert finding["evidence"] == "API_KEY = <redacted>"
    assert finding["policy_action"] == "block"
    assert finding["blocking"] is True

    events = _read_jsonl(tmp_path / summary.artifacts["events"])
    event_types = [event["type"] for event in events]
    assert "context_manifest_created" not in event_types
    assert "provider_selected" not in event_types
    assert "model_action" not in event_types

    assert main(["export", "sarif", summary.run_id]) == 0
    capsys.readouterr()
    exported = json.loads(
        (tmp_path / ".agent-harness" / "exports" / f"{summary.run_id}.sarif").read_text(
            encoding="utf-8"
        )
    )
    result = next(
        result
        for result in exported["runs"][0]["results"]
        if result["ruleId"] == "credential-literal"
    )
    assert result["properties"]["policy_action"] == "block"
    assert result["properties"]["blocking"] is True
    assert result["properties"]["evidence"] == "API_KEY = <redacted>"


def test_medium_security_finding_is_report_only_by_default(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    (tmp_path / "review.py").write_text(
        "# TODO: security review\n\ndef identity(value):\n    return value\n",
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v1",
            "task_id": "medium-security-report",
            "title": "Inspect reviewed file",
            "intent": "Inspect the target without changing files.",
            "target_paths": ["review.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-medium-security-report")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:15:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "completed"
    findings = json.loads((tmp_path / summary.artifacts["security_findings"]).read_text())
    assert findings["gate"]["status"] == "passed"
    assert findings["findings"][0]["severity"] == "medium"


def test_security_findings_export_to_sarif_and_doctor_reports_optional_scanners(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    relaxed = dict(DEFAULT_POLICY)
    relaxed["name"] = "relaxed-security"
    relaxed["security_fail_threshold"] = "critical"
    (tmp_path / "policies" / "relaxed-security.json").write_text(
        json.dumps(relaxed, indent=2), encoding="utf-8"
    )
    (tmp_path / "dangerous.py").write_text(
        "import subprocess\n\nsubprocess.run(command, shell=True)\n",
        encoding="utf-8",
    )
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v1",
            "task_id": "security-sarif",
            "title": "Inspect dangerous file",
            "intent": "Inspect the target without changing files.",
            "policy_profile": "relaxed-security",
            "target_paths": ["dangerous.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-security-sarif")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:20:00Z")
    HarnessRuntime(tmp_path).run_task(task_path)

    assert main(["export", "sarif", "run-security-sarif"]) == 0
    capsys.readouterr()
    exported = json.loads(
        (tmp_path / ".agent-harness" / "exports" / "run-security-sarif.sarif").read_text(
            encoding="utf-8"
        )
    )
    results = exported["runs"][0]["results"]
    assert any(result["ruleId"] == "python-dangerous-shell" for result in results)

    assert main(["doctor"]) == 0
    doctor = capsys.readouterr().out
    assert "optional scanner" in doctor
    assert "first-party security checks active" in doctor


def test_advisory_scanner_reports_are_recorded_without_blocking_runs(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    advisory_dir = tmp_path / ".agent-harness" / "advisories"
    advisory_dir.mkdir(parents=True)
    (advisory_dir / "gitleaks.json").write_text(
        json.dumps({"findings": [{"rule": "example-secret"}]}, indent=2),
        encoding="utf-8",
    )
    (advisory_dir / "cyclonedx.json").write_text(
        json.dumps({"bomFormat": "CycloneDX", "components": []}, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "safe.py").write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = _write_task(
        tmp_path,
        {
            "schema_version": "task.v2",
            "task_id": "advisory-scanner-reports",
            "title": "Inspect safe file",
            "intent": "Inspect the target without changing files.",
            "target_paths": ["safe.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 3,
        },
    )
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-advisory-scanners")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T21:25:00Z")

    summary = HarnessRuntime(tmp_path).run_task(task_path)

    assert summary.status == "completed"
    assert "advisory_reports" in summary.artifacts
    advisory_report = json.loads((tmp_path / summary.artifacts["advisory_reports"]).read_text())
    reports = {report["kind"]: report for report in advisory_report["reports"]}
    assert reports["gitleaks"]["available"] is True
    assert reports["gitleaks"]["policy_action"] == "advisory"
    assert reports["gitleaks"]["blocking"] is False
    assert reports["cyclonedx"]["available"] is True
    assert reports["cyclonedx"]["policy_action"] == "advisory"
    assert reports["cyclonedx"]["blocking"] is False

    monkeypatch.setenv("PATH", "")
    assert main(["doctor"]) == 0
    doctor = capsys.readouterr().out
    assert "WARN optional scanner: gitleaks unavailable" in doctor
    assert "WARN optional scanner: cyclonedx unavailable" in doctor


def _seed_project_with_mock_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "mock-default",
        "provider_profiles": [
            {
                "provider_profile_id": "mock-default",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic-default",
                "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
                "network": False,
                "requires_approval": False,
            }
        ],
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8"
    )


def _write_task(root: Path, payload: dict[str, object]) -> Path:
    path = root / "task.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
