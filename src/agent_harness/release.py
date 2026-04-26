from __future__ import annotations

import json
import subprocess
import tomllib
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
    version: str | None = None,
    output: Path | None = None,
    ci_run_id: str | None = None,
) -> dict[str, Any]:
    normalized_version = (version or _project_version(project_root)).removeprefix("v")
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
    package = _package_evidence(project_root, normalized_version)
    demos = _demo_evidence(project_root)
    docs = _docs_evidence(project_root, docs_report)
    templates = _template_evidence(project_root)
    release_artifacts = _release_artifact_evidence(project_root, normalized_version)
    diagnostics = _diagnostics(
        package=package,
        demos=demos,
        docs=docs,
        templates=templates,
        release_artifacts=release_artifacts,
        changelog_present=changelog_present,
        tag_exists=tag_exists,
        tag_pushed=tag_pushed,
        remote_ci=remote_ci,
    )
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
            if not diagnostics
            and docs_report["status"] == "passed"
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
        "package": package,
        "demos": demos,
        "docs": docs,
        "templates": templates,
        "release_artifacts": release_artifacts,
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
        "diagnostics": diagnostics,
        "report_path": str(report_path.resolve()),
    }
    write_json(report_path, report)
    return report


def _project_version(project_root: Path) -> str:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        raise FileNotFoundError("pyproject.toml is required to infer release version")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml must define [project].version")
    version = project.get("version")
    if not isinstance(version, str):
        raise ValueError("pyproject.toml must define [project].version")
    return version


def _package_evidence(project_root: Path, version: str) -> dict[str, Any]:
    wheel = _matching_files(project_root, f"dist/agent_harness-{version}-*.whl")
    sdist = _matching_files(project_root, f"dist/agent_harness-{version}.tar.gz")
    artifacts_present = bool(wheel and sdist)
    build_evidence = _release_evidence(project_root, "package-build")
    clean_install_evidence = _release_evidence(project_root, "clean-install")
    console_script_evidence = _release_evidence(project_root, "console-script")
    return {
        "build": {
            "command": "python -m build",
            "status": (
                "passed"
                if artifacts_present and build_evidence["status"] == "passed"
                else "missing_evidence"
            ),
            "artifacts": [*wheel, *sdist],
            "evidence": build_evidence["path"],
            "action": "Run python -m build and keep the wheel and sdist under dist/.",
        },
        "clean_install": {
            "command": f"python -m pip install dist/agent_harness-{version}-*.whl",
            "status": (
                "blocked"
                if not wheel
                else _evidence_status(clean_install_evidence)
            ),
            "evidence": clean_install_evidence["path"],
            "action": (
                "Build the wheel, install it in a clean environment, and record "
                "the result before release."
            ),
        },
        "console_script": {
            "command": "agent-harness doctor",
            "status": _evidence_status(console_script_evidence),
            "evidence": console_script_evidence["path"],
            "action": (
                "After clean install, run the installed agent-harness console "
                "script and record the result."
            ),
        },
    }


def _demo_evidence(project_root: Path) -> dict[str, Any]:
    provider_audit_evidence = _release_evidence(project_root, "demo-provider-audit")
    python_refactor_evidence = _release_evidence(project_root, "demo-python-refactor")
    return {
        "provider-audit": {
            "command": "agent-harness demo provider-audit",
            "status": _evidence_status(provider_audit_evidence),
            "evidence": provider_audit_evidence["path"],
            "action": "Run the provider-audit demo and record the inspectable run id.",
        },
        "python-refactor": {
            "command": "agent-harness run examples/tasks/python_refactor.json --dry-run",
            "status": _evidence_status(python_refactor_evidence),
            "evidence": python_refactor_evidence["path"],
            "action": "Run the Python refactor demo path and record the resulting run id.",
        },
    }


def _docs_evidence(project_root: Path, docs_report: dict[str, Any]) -> dict[str, Any]:
    compatibility_path = project_root / "docs" / "prd-agent-harness-v3.md"
    return {
        "check": {
            "command": "agent-harness docs check",
            "status": docs_report["status"],
            "findings": docs_report["counts"]["findings"],
        },
        "schema_compatibility": {
            "path": "docs/prd-agent-harness-v3.md",
            "present": compatibility_path.exists(),
            "status": "passed" if compatibility_path.exists() else "missing_evidence",
            "action": "Document the public schema compatibility policy in the V3 PRD.",
        },
        "roadmap_claims": {
            "command": "agent-harness docs check",
            "status": docs_report["status"],
            "action": "Resolve docs-check findings before release.",
        },
    }


def _template_evidence(project_root: Path) -> dict[str, Any]:
    evidence = _release_evidence(project_root, "template-validation")
    return {
        "validation": {
            "command": "agent-harness template validate --all",
            "status": _evidence_status(evidence),
            "evidence": evidence["path"],
            "action": "Run bundled template validation and record the report.",
        }
    }


def _release_artifact_evidence(project_root: Path, version: str) -> dict[str, Any]:
    wheel_glob = f"dist/agent_harness-{version}-*.whl"
    sdist_glob = f"dist/agent_harness-{version}.tar.gz"
    wheel = _matching_files(project_root, wheel_glob)
    sdist = _matching_files(project_root, sdist_glob)
    return {
        "wheel": {
            "expected_glob": wheel_glob,
            "status": "passed" if wheel else "missing_evidence",
            "files": wheel,
            "action": "Build and verify the release wheel.",
        },
        "sdist": {
            "expected_glob": sdist_glob,
            "status": "passed" if sdist else "missing_evidence",
            "files": sdist,
            "action": "Build and verify the release source distribution.",
        },
    }


def _matching_files(project_root: Path, pattern: str) -> list[str]:
    return sorted(path.as_posix() for path in project_root.glob(pattern) if path.is_file())


def _release_evidence(project_root: Path, name: str) -> dict[str, str]:
    relative = Path(".agent-harness") / "release" / "evidence" / f"{name}.json"
    path = project_root / relative
    if not path.exists():
        return {"status": "missing_evidence", "path": relative.as_posix()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "failed", "path": relative.as_posix()}
    status = payload.get("status") if isinstance(payload, dict) else None
    return {
        "status": "passed" if status == "passed" else "failed",
        "path": relative.as_posix(),
    }


def _evidence_status(evidence: dict[str, str]) -> str:
    return evidence["status"]


def _diagnostics(
    *,
    package: dict[str, Any],
    demos: dict[str, Any],
    docs: dict[str, Any],
    templates: dict[str, Any],
    release_artifacts: dict[str, Any],
    changelog_present: bool,
    tag_exists: bool,
    tag_pushed: bool,
    remote_ci: dict[str, Any],
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    _collect_status_diagnostics(diagnostics, "package", package)
    _collect_status_diagnostics(diagnostics, "demos", demos)
    _collect_status_diagnostics(diagnostics, "docs", docs)
    _collect_status_diagnostics(diagnostics, "templates", templates)
    _collect_status_diagnostics(diagnostics, "release_artifacts", release_artifacts)
    if not changelog_present:
        diagnostics.append(
            {
                "gate": "changelog",
                "status": "missing_evidence",
                "action": "Add a CHANGELOG.md entry for the release version.",
            }
        )
    if not tag_exists:
        diagnostics.append(
            {
                "gate": "tag.local",
                "status": "missing_evidence",
                "action": "Create the local release tag after final verification.",
            }
        )
    if not tag_pushed:
        diagnostics.append(
            {
                "gate": "tag.remote",
                "status": "missing_evidence",
                "action": "Create and push the release tag after final verification.",
            }
        )
    if not _required_remote_ci_passed(remote_ci):
        diagnostics.append(
            {
                "gate": "remote_ci",
                "status": "missing_evidence",
                "action": "Record a passing GitHub Actions CI run for the target commit.",
            }
        )
    return diagnostics


def _collect_status_diagnostics(
    diagnostics: list[dict[str, str]],
    prefix: str,
    node: dict[str, Any],
) -> None:
    for key, value in node.items():
        if not isinstance(value, dict):
            continue
        status = value.get("status")
        if status in {None, "passed"}:
            _collect_status_diagnostics(diagnostics, f"{prefix}.{key}", value)
            continue
        action = value.get("action")
        diagnostics.append(
            {
                "gate": f"{prefix}.{key}",
                "status": str(status),
                "action": str(action or f"Resolve {prefix}.{key} before release."),
            }
        )


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
