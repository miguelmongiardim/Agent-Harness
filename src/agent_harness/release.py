from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from agent_harness.docs_check import run_docs_check
from agent_harness.utils import now_utc, write_json

LOCAL_RELEASE_CHECKS = {
    "pytest": "python -m pytest -q",
    "docs_check": "agent-harness docs check",
    "ruff": "python -m ruff check src tests",
    "mypy": "python -m mypy",
    "compileall": "python -m compileall -q src tests",
    "diff_check": "git diff --check",
    "eval": "agent-harness eval",
}


def build_release_readiness_report(
    project_root: Path,
    version: str,
    output: Path | None = None,
) -> dict[str, Any]:
    normalized_version = version.removeprefix("v")
    tag_name = f"v{normalized_version}"
    docs_report = run_docs_check(project_root)
    changelog_present = _changelog_entry_present(project_root, normalized_version)
    target_commit = _git_output(project_root, ["git", "rev-parse", "HEAD"])
    advisory_root = project_root / ".agent-harness" / "advisories"
    report_path = output or (
        project_root
        / ".agent-harness"
        / "release"
        / f"{tag_name}-readiness.json"
    )
    tag_exists = _tag_exists(project_root, tag_name)
    report = {
        "schema_version": "release_readiness.v1",
        "version": normalized_version,
        "generated_at": now_utc().isoformat(),
        "status": (
            "ready"
            if docs_report["status"] == "passed" and changelog_present and tag_exists
            else "pending"
        ),
        "tag": {
            "name": tag_name,
            "target_commit": target_commit,
            "pushed": tag_exists,
        },
        "changelog": {
            "entry": normalized_version,
            "present": changelog_present,
            "path": "CHANGELOG.md",
        },
        "docs_gate": {
            "command": "agent-harness docs check",
            "status": docs_report["status"],
            "findings": docs_report["counts"]["findings"],
        },
        "local_checks": {
            name: {
                "command": command,
                "status": "represented",
            }
            for name, command in LOCAL_RELEASE_CHECKS.items()
        },
        "remote_ci": {
            "python_3_11": {"required": True, "status": "not_recorded"},
            "python_3_12": {"required": True, "status": "not_recorded"},
            "python_3_13": {"allowed_failure": True, "status": "not_recorded"},
        },
        "advisory_reports": {
            "gitleaks": _advisory_report(advisory_root, "gitleaks.json"),
            "cyclonedx": _advisory_report(advisory_root, "cyclonedx.json"),
        },
        "report_path": str(report_path.resolve()),
    }
    write_json(report_path, report)
    return report


def _changelog_entry_present(project_root: Path, version: str) -> bool:
    changelog = project_root / "CHANGELOG.md"
    if not changelog.exists():
        return False
    text = changelog.read_text(encoding="utf-8")
    return f"## [{version}]" in text


def _tag_exists(project_root: Path, tag_name: str) -> bool:
    return bool(_git_output(project_root, ["git", "tag", "--list", tag_name]))


def _git_output(project_root: Path, args: list[str]) -> str:
    result = subprocess.run(
        args,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _advisory_report(advisory_root: Path, filename: str) -> dict[str, object]:
    path = advisory_root / filename
    return {
        "required": False,
        "present": path.exists(),
        "path": path.relative_to(advisory_root.parent.parent).as_posix(),
    }
