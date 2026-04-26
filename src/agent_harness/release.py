from __future__ import annotations

import json
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
    ci_run_id: str | None = None,
) -> dict[str, Any]:
    normalized_version = version.removeprefix("v")
    tag_name = f"v{normalized_version}"
    docs_report = run_docs_check(project_root)
    changelog_present = _changelog_entry_present(project_root, normalized_version)
    tag_exists = _tag_exists(project_root, tag_name)
    tag_pushed = _tag_pushed(project_root, tag_name)
    target_commit = _tag_target_commit(project_root, tag_name) or _git_output(
        project_root, ["git", "rev-parse", "HEAD"]
    )
    remote_ci = _remote_ci_evidence(project_root, target_commit, ci_run_id)
    advisory_root = project_root / ".agent-harness" / "advisories"
    report_path = output or (
        project_root
        / ".agent-harness"
        / "release"
        / f"{tag_name}-readiness.json"
    )
    report = {
        "schema_version": "release_readiness.v1",
        "version": normalized_version,
        "generated_at": now_utc().isoformat(),
        "status": (
            "ready"
            if docs_report["status"] == "passed"
            and changelog_present
            and tag_exists
            and tag_pushed
            and _required_remote_ci_passed(remote_ci)
            else "pending"
        ),
        "tag": {
            "name": tag_name,
            "target_commit": target_commit,
            "pushed": tag_pushed,
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
        "remote_ci": remote_ci,
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


def _tag_target_commit(project_root: Path, tag_name: str) -> str:
    return _git_output(project_root, ["git", "rev-list", "-n", "1", tag_name])


def _tag_pushed(project_root: Path, tag_name: str) -> bool:
    return bool(
        _git_output(project_root, ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag_name}"])
    )


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


def _remote_ci_evidence(
    project_root: Path,
    target_commit: str,
    ci_run_id: str | None,
) -> dict[str, Any]:
    run = _github_run(project_root, target_commit, ci_run_id)
    evidence = _empty_remote_ci()
    if not run:
        return evidence

    run_head = str(run.get("headSha") or "")
    run_status = str(run.get("status") or "unknown")
    run_conclusion = run.get("conclusion")
    evidence["run"] = {
        "source": "github_actions",
        "run_id": run.get("databaseId"),
        "url": run.get("url"),
        "head_sha": run_head,
        "status": run_status,
        "conclusion": run_conclusion,
        "matches_target_commit": run_head == target_commit,
    }
    if run_head != target_commit:
        return evidence

    jobs = run.get("jobs")
    if not isinstance(jobs, list):
        return evidence

    for version in ("3.11", "3.12", "3.13"):
        key = f"python_{version.replace('.', '_')}"
        job = _find_ci_job(jobs, f"compatibility ({version})")
        if job is None:
            continue
        conclusion = job.get("conclusion")
        status = "passed" if conclusion == "success" else "failed"
        if version == "3.13" and conclusion not in {"success", None}:
            status = "failed_allowed"
        evidence[key].update(
            {
                "status": status,
                "job": job.get("name"),
                "url": job.get("url"),
                "conclusion": conclusion,
            }
        )
    return evidence


def _empty_remote_ci() -> dict[str, Any]:
    return {
        "run": {"source": "not_recorded", "status": "not_recorded"},
        "python_3_11": {"required": True, "status": "not_recorded"},
        "python_3_12": {"required": True, "status": "not_recorded"},
        "python_3_13": {"allowed_failure": True, "status": "not_recorded"},
    }


def _github_run(
    project_root: Path,
    target_commit: str,
    ci_run_id: str | None,
) -> dict[str, Any] | None:
    if ci_run_id:
        run = _gh_json(
            project_root,
            [
                "gh",
                "run",
                "view",
                ci_run_id,
                "--json",
                "databaseId,status,conclusion,jobs,url,headSha",
            ],
        )
        return run if isinstance(run, dict) else None
    runs = _gh_json(
        project_root,
        [
            "gh",
            "run",
            "list",
            "--commit",
            target_commit,
            "--limit",
            "5",
            "--json",
            "databaseId,status,conclusion,name,headSha,url",
        ],
    )
    if not isinstance(runs, list):
        return None
    for run in runs:
        if isinstance(run, dict) and run.get("name") == "CI" and run.get("databaseId"):
            return _github_run(project_root, target_commit, str(run["databaseId"]))
    return None


def _gh_json(project_root: Path, args: list[str]) -> Any:
    try:
        result = subprocess.run(
            args,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _find_ci_job(jobs: list[Any], name: str) -> dict[str, Any] | None:
    for job in jobs:
        if isinstance(job, dict) and job.get("name") == name:
            return job
    return None


def _required_remote_ci_passed(remote_ci: dict[str, Any]) -> bool:
    run = remote_ci.get("run")
    if not isinstance(run, dict) or run.get("conclusion") != "success":
        return False
    for key in ("python_3_11", "python_3_12"):
        entry = remote_ci.get(key)
        if not isinstance(entry, dict) or entry.get("status") != "passed":
            return False
    return True


def _advisory_report(advisory_root: Path, filename: str) -> dict[str, object]:
    path = advisory_root / filename
    return {
        "required": False,
        "present": path.exists(),
        "path": path.relative_to(advisory_root.parent.parent).as_posix(),
    }
