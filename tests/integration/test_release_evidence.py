from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main


def test_release_readiness_report_requires_docs_checks_ci_advisories_and_changelog(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["release", "readiness", "--version", "0.3.0"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "release_readiness.v1"
    assert report["version"] == "0.3.0"
    assert report["tag"]["name"] == "v0.3.0"
    assert report["tag"]["target_commit"]
    assert report["changelog"]["entry"] == "0.3.0"
    assert report["changelog"]["present"] is True
    assert report["docs_gate"]["command"] == "agent-harness docs check"
    assert report["docs_gate"]["status"] in {"passed", "failed"}

    local_checks = report["local_checks"]
    assert set(local_checks) == {
        "pytest",
        "docs_check",
        "ruff",
        "mypy",
        "compileall",
        "diff_check",
        "eval",
    }
    assert all(check["command"] for check in local_checks.values())

    remote_ci = report["remote_ci"]
    assert remote_ci["python_3_11"]["required"] is True
    assert remote_ci["python_3_12"]["required"] is True
    assert remote_ci["python_3_13"]["allowed_failure"] is True

    advisory = report["advisory_reports"]
    assert advisory["gitleaks"]["required"] is False
    assert advisory["cyclonedx"]["required"] is False
    assert advisory["gitleaks"]["path"].endswith("gitleaks.json")
    assert advisory["cyclonedx"]["path"].endswith("cyclonedx.json")

    assert report["status"] in {"ready", "pending"}
    assert Path(report["report_path"]).exists()
