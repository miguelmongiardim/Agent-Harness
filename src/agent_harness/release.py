from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import tomllib
from importlib import resources
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_harness.config import load_mapping
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.docs_check import run_docs_check
from agent_harness.utils import hash_file, now_utc, write_json

LOCAL_RELEASE_CHECKS = {
    "pytest": "python -m pytest -q",
    "docs_check": "agent-harness docs check",
    "ruff": "python -m ruff check src tests",
    "mypy": "python -m mypy",
    "compileall": "python -m compileall -q src tests",
    "diff_check": "git diff --check",
    "eval": "agent-harness eval",
}

RELEASE_EVIDENCE_DIR = Path(".agent-harness") / "release" / "evidence"
OPERATOR_STATIC_PACKAGE_DATA = [
    "operator/static/*.html",
    "operator/static/*.css",
    "operator/static/*.js",
]
OPERATOR_STATIC_ASSETS = ["index.html", "app.css", "app.js"]
OPERATOR_FORBIDDEN_REMOTE_MARKERS = (
    "http://",
    "https://",
    "//cdn",
    "googleapis",
    "gstatic",
    "analytics",
    "localStorage",
    "sessionStorage",
)


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
    retrieval = _retrieval_evidence(project_root)
    operator = _operator_evidence(project_root)
    release_artifacts = _release_artifact_evidence(project_root, normalized_version)
    diagnostics = _diagnostics(
        package=package,
        demos=demos,
        docs=docs,
        templates=templates,
        retrieval=retrieval,
        operator=operator,
        release_artifacts=release_artifacts,
        changelog_present=changelog_present,
        tag_exists=tag_exists,
        tag_pushed=tag_pushed,
        remote_ci=remote_ci,
    )
    report_path = output or (
        project_root / ".agent-harness" / "release" / f"{tag_name}-readiness.json"
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
        "retrieval": retrieval,
        "operator": operator,
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


def build_release_package_check_report(
    project_root: Path,
    version: str | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    normalized_version = (version or _project_version(project_root)).removeprefix("v")
    release_root = project_root / ".agent-harness" / "release"
    release_root.mkdir(parents=True, exist_ok=True)

    build = _run_command(
        [sys.executable, "-m", "build", "--outdir", "dist"],
        cwd=project_root,
        timeout_seconds=300,
    )
    wheel_paths = [
        project_root / path
        for path in _matching_files(project_root, f"dist/agent_harness-{normalized_version}-*.whl")
    ]
    sdist_paths = [
        project_root / path
        for path in _matching_files(project_root, f"dist/agent_harness-{normalized_version}.tar.gz")
    ]
    wheel = wheel_paths[0] if wheel_paths else None
    sdist = sdist_paths[0] if sdist_paths else None
    build_status = (
        "passed"
        if build["status"] == "passed" and wheel is not None and sdist is not None
        else "failed"
    )
    build_evidence = {
        **build,
        "status": build_status,
        "artifacts": {
            "wheel": _artifact_record(project_root, wheel),
            "sdist": _artifact_record(project_root, sdist),
        },
    }
    _write_release_evidence(project_root, "package-build", build_evidence)

    install = _skipped_result("clean install skipped because package build failed")
    console = _skipped_result("console script skipped because clean install failed")
    if build_status == "passed" and wheel is not None:
        with tempfile.TemporaryDirectory(
            prefix="package-check-",
            dir=release_root,
        ) as temp_dir:
            venv_path = Path(temp_dir) / "venv"
            create_venv = _run_command(
                [sys.executable, "-m", "venv", str(venv_path)],
                cwd=project_root,
                timeout_seconds=120,
            )
            if create_venv["status"] == "passed":
                install = _run_command(
                    [
                        str(_venv_python(venv_path)),
                        "-m",
                        "pip",
                        "install",
                        str(wheel),
                    ],
                    cwd=project_root,
                    timeout_seconds=300,
                )
                install = {
                    **install,
                    "venv": str(venv_path),
                    "wheel": _project_relative(project_root, wheel),
                }
                if install["status"] == "passed":
                    console = _run_command(
                        [str(_console_script(venv_path)), "doctor"],
                        cwd=project_root,
                        timeout_seconds=120,
                    )
                    console = {
                        **console,
                        "venv": str(venv_path),
                    }
            else:
                install = create_venv

    _write_release_evidence(project_root, "clean-install", install)
    _write_release_evidence(project_root, "console-script", console)

    status = (
        "passed"
        if build_status == "passed"
        and install["status"] == "passed"
        and console["status"] == "passed"
        else "failed"
    )
    report_path = output or release_root / "package-check.json"
    report = {
        "schema_version": "release_package_check.v1",
        "version": normalized_version,
        "generated_at": now_utc().isoformat(),
        "status": status,
        "build": build_evidence,
        "clean_install": install,
        "console_script": console,
        "artifacts": {
            "wheel": _artifact_record(project_root, wheel),
            "sdist": _artifact_record(project_root, sdist),
        },
        "evidence": {
            "package_build": (RELEASE_EVIDENCE_DIR / "package-build.json").as_posix(),
            "clean_install": (RELEASE_EVIDENCE_DIR / "clean-install.json").as_posix(),
            "console_script": (RELEASE_EVIDENCE_DIR / "console-script.json").as_posix(),
        },
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
            "status": ("blocked" if not wheel else _evidence_status(clean_install_evidence)),
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
        "migration_notes": _required_doc_markers(
            project_root,
            "docs/migration.md",
            ("v0.3.0", "v1.0.0"),
            "Document the migration notes from v0.3.0 to v1.0.0.",
        ),
        "release_process": _required_doc_markers(
            project_root,
            "docs/release-readiness.md",
            ("Release Checklist", "Tag Process", "Artifact Verification"),
            "Document the release checklist, tag process, and artifact verification steps.",
        ),
    }


def _required_doc_markers(
    project_root: Path,
    relative_path: str,
    required_markers: tuple[str, ...],
    action: str,
) -> dict[str, Any]:
    path = project_root / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "present": False,
            "status": "missing_evidence",
            "missing_markers": list(required_markers),
            "action": action,
        }
    text = path.read_text(encoding="utf-8")
    missing_markers = [marker for marker in required_markers if marker not in text]
    return {
        "path": relative_path,
        "present": True,
        "status": "passed" if not missing_markers else "missing_evidence",
        "missing_markers": missing_markers,
        "action": action,
    }


def _template_evidence(project_root: Path) -> dict[str, Any]:
    _run_template_validation_evidence(project_root)
    evidence = _release_evidence(project_root, "template-validation")
    return {
        "validation": {
            "command": "agent-harness template validate --all",
            "status": _evidence_status(evidence),
            "evidence": evidence["path"],
            "action": "Run bundled template validation and record the report.",
        },
        "bundled_pack_acceptance": _bundled_template_pack_acceptance(project_root),
        "remote_catalog_defaults": _template_remote_catalog_defaults(project_root),
    }


def _run_template_validation_evidence(project_root: Path) -> dict[str, Any]:
    from agent_harness.templates.validation import validate_templates

    try:
        return validate_templates(project_root, all_templates=True)
    except Exception as exc:
        report = {
            "schema_version": "template_validation.v1",
            "status": "failed",
            "generated_at": now_utc().isoformat(),
            "templates": [],
            "message": _safe_error(exc),
        }
        _write_release_evidence(project_root, "template-validation", report)
        return report


def _bundled_template_pack_acceptance(project_root: Path) -> dict[str, Any]:
    from agent_harness.config import write_default_config
    from agent_harness.policy import PolicyEngine, load_policy
    from agent_harness.templates.apply import resolve_template_parameters
    from agent_harness.templates.registry import list_templates, load_template
    from agent_harness.templates.validation import validate_bundled_template_pack

    release_root = project_root / ".agent-harness" / "release"
    release_root.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="template-pack-acceptance-", dir=release_root))
    catalog_root = work_root / "_catalog"
    catalog_root.mkdir(parents=True)
    write_default_config(catalog_root, force=True)
    write_json(catalog_root / "policies" / "default.json", DEFAULT_POLICY)
    records = [
        record for record in list_templates(catalog_root) if record.source_type == "bundled_pack"
    ]
    template_ids = sorted(record.template_id for record in records)
    packs: list[dict[str, Any]] = []
    for template_id in template_ids:
        sandbox = work_root / template_id
        sandbox.mkdir(parents=True)
        write_default_config(sandbox, force=True)
        write_json(sandbox / "policies" / "default.json", DEFAULT_POLICY)

        detail = load_template(template_id, sandbox)
        parameters = resolve_template_parameters(detail, {})
        policy = PolicyEngine(sandbox, load_policy(sandbox, "default"))
        target = sandbox / "scaffold"

        validation = validate_bundled_template_pack(template_id)
        dry_run = _template_pack_dry_run_evidence(
            sandbox,
            detail,
            target,
            policy,
            parameters,
        )
        clean_apply = _template_pack_clean_apply_evidence(
            sandbox,
            template_id,
            target,
            parameters,
        )
        generated_examples = _generated_template_examples_evidence(
            target,
            clean_apply.get("summary", {}),
        )
        application_evidence = _template_application_record_evidence(
            sandbox,
            clean_apply.get("summary", {}),
            template_id,
        )
        docs = _template_docs_evidence(target, detail)
        pack: dict[str, Any] = {
            "template_id": template_id,
            "validation": {
                "status": validation["status"],
                "diagnostics": validation.get("diagnostics", []),
            },
            "dry_run": dry_run,
            "clean_apply": {
                key: value for key, value in clean_apply.items() if key != "summary"
            },
            "generated_examples": generated_examples,
            "application_evidence": application_evidence,
            "docs": docs,
        }
        pack["status"] = (
            "passed"
            if all(
                pack[gate]["status"] == "passed"
                for gate in (
                    "validation",
                    "dry_run",
                    "clean_apply",
                    "generated_examples",
                    "application_evidence",
                    "docs",
                )
            )
            else "failed"
        )
        packs.append(pack)

    report = {
        "command": "agent-harness release readiness",
        "status": (
            "passed" if packs and all(pack["status"] == "passed" for pack in packs) else "failed"
        ),
        "schema_version": "template_pack_acceptance.v1",
        "template_ids": template_ids,
        "work_root": _project_relative(project_root, work_root),
        "packs": packs,
        "action": (
            "Ensure every bundled V7 pack validates, dry-runs, clean-applies, "
            "generates valid config/task/policy/eval examples, records "
            "template_application.v1 evidence, and includes docs."
        ),
    }
    _write_release_evidence(project_root, "template-pack-acceptance", report)
    return report


def _template_pack_dry_run_evidence(
    sandbox: Path,
    detail: Any,
    target: Path,
    policy: Any,
    parameters: dict[str, str],
) -> dict[str, Any]:
    from agent_harness.templates.apply import build_template_application_evidence

    before = _relative_files(sandbox)
    try:
        evidence = build_template_application_evidence(
            detail,
            target,
            policy,
            parameters=parameters,
            mode="dry_run",
        )
    except Exception as exc:
        return {
            "status": "failed",
            "detail": _safe_error(exc),
            "mutated_files": [],
        }
    after = _relative_files(sandbox)
    mutated_files = sorted(after - before)
    return {
        "status": (
            "passed"
            if evidence.get("schema_version") == "template_application.v1"
            and evidence.get("status") == "planned"
            and evidence.get("mode") == "dry_run"
            and not mutated_files
            else "failed"
        ),
        "mode": evidence.get("mode"),
        "planned_files": evidence.get("planned_files", []),
        "approval_required": evidence.get("approval_required"),
        "mutated_files": mutated_files,
    }


def _template_pack_clean_apply_evidence(
    sandbox: Path,
    template_id: str,
    target: Path,
    parameters: dict[str, str],
) -> dict[str, Any]:
    from agent_harness.core.runtime import HarnessRuntime

    try:
        summary = HarnessRuntime(sandbox).apply_template(
            template_id,
            target,
            parameters=parameters,
        )
    except Exception as exc:
        return {
            "status": "failed",
            "detail": _safe_error(exc),
            "summary": {},
        }
    summary_payload = summary.model_dump(mode="json")
    return {
        "status": "passed" if summary.status == "completed" and not summary.approvals else "failed",
        "run_id": summary.run_id,
        "target": _project_relative(sandbox, target),
        "artifacts": summary_payload.get("artifacts", {}),
        "summary": summary_payload,
    }


def _generated_template_examples_evidence(
    target: Path,
    summary: dict[str, Any],
) -> dict[str, Any]:
    del summary
    from agent_harness.schemas import EvalSpec, HarnessConfig, PolicyProfile, TaskSpec

    models: dict[str, type[Any]] = {
        "config.v2": HarnessConfig,
        "policy.v2": PolicyProfile,
        "task.v2": TaskSpec,
        "eval.v1": EvalSpec,
    }
    examples: dict[str, str] = {}
    diagnostics: list[dict[str, str]] = []
    for path in sorted(target.rglob("*.json")):
        relative = _project_relative(target, path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(
                {
                    "path": relative,
                    "schema_version": "",
                    "detail": f"invalid JSON: {exc}",
                }
            )
            continue
        if not isinstance(payload, dict):
            continue
        schema_version = payload.get("schema_version")
        if not isinstance(schema_version, str) or schema_version not in models:
            continue
        try:
            models[schema_version].model_validate(payload)
        except Exception as exc:
            diagnostics.append(
                {
                    "path": relative,
                    "schema_version": schema_version,
                    "detail": _safe_error(exc),
                }
            )
            continue
        examples[schema_version] = relative
    missing = sorted(set(models) - set(examples))
    return {
        "status": "passed" if not missing and not diagnostics else "failed",
        "examples": examples,
        "missing_schema_versions": missing,
        "diagnostics": diagnostics,
        "action": (
            "Generated template examples must validate as config.v2, policy.v2, "
            "task.v2, and eval.v1."
        ),
    }


def _template_application_record_evidence(
    sandbox: Path,
    summary: dict[str, Any],
    template_id: str,
) -> dict[str, Any]:
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        return {
            "status": "missing_evidence",
            "path": None,
            "action": "Clean applies must record template_application.v1 evidence.",
        }
    relative = artifacts.get("template_application")
    if not isinstance(relative, str):
        return {
            "status": "missing_evidence",
            "path": None,
            "action": "Clean applies must record template_application.v1 evidence.",
        }
    path = sandbox / relative
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "path": relative,
            "detail": _safe_error(exc),
            "action": "Clean applies must record readable template_application.v1 evidence.",
        }
    status = (
        "passed"
        if payload.get("schema_version") == "template_application.v1"
        and payload.get("status") == "completed"
        and payload.get("mode") == "apply"
        and payload.get("template_id") == template_id
        and payload.get("created_files")
        else "failed"
    )
    return {
        "status": status,
        "path": relative,
        "created_files": payload.get("created_files", []),
        "action": "Clean applies must record completed template_application.v1 evidence.",
    }


def _template_docs_evidence(target: Path, detail: Any) -> dict[str, Any]:
    declared_docs = sorted(
        file.path
        for file in detail.files
        if file.path == "README.md" or file.path.startswith("docs/") or file.path.endswith(".md")
    )
    missing_docs = [path for path in declared_docs if not (target / path).exists()]
    return {
        "status": "passed" if declared_docs and not missing_docs else "missing_evidence",
        "files": declared_docs,
        "missing_files": missing_docs,
        "action": "Bundled template packs must include README or docs content.",
    }


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _template_remote_catalog_defaults(project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, object]] = []
    for path in _template_config_paths(project_root):
        try:
            config = load_mapping(path)
        except Exception as exc:
            findings.append(
                {
                    "path": _project_relative(project_root, path),
                    "setting": "parse_error",
                    "value": str(exc),
                }
            )
            continue
        findings.extend(_remote_template_catalog_findings(project_root, path, config))
    return {
        "status": "failed" if findings else "passed",
        "checked_paths": [
            _project_relative(project_root, path)
            for path in _template_config_paths(project_root)
        ],
        "remote_defaults": findings,
        "action": (
            "Keep executable template configuration on bundled/local sources; "
            "remote catalogs, marketplace URLs, and cloud registries are not V7 defaults."
        ),
    }


def _template_config_paths(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    root_config = project_root / "agent-harness.yaml"
    if root_config.exists():
        paths.append(root_config)
    examples = project_root / "examples"
    if examples.exists():
        paths.extend(sorted(examples.rglob("agent-harness.yaml")))
        paths.extend(sorted(examples.rglob("config.v2.yaml")))
        paths.extend(sorted(examples.rglob("config.v2.json")))
        paths.extend(sorted(examples.rglob("*.config.json")))
    return sorted(dict.fromkeys(paths))


def _remote_template_catalog_findings(
    project_root: Path,
    path: Path,
    config: dict[str, Any],
) -> list[dict[str, object]]:
    relative = _project_relative(project_root, path)
    findings: list[dict[str, object]] = []
    catalog = config.get("template_catalog")
    if isinstance(catalog, str) and _remote_template_catalog_value(catalog):
        findings.append(
            {
                "path": relative,
                "setting": "template_catalog",
                "value": catalog,
            }
        )
    templates = config.get("templates")
    if isinstance(templates, dict):
        for setting in (
            "catalog_url",
            "remote_catalog",
            "remote_catalog_url",
            "marketplace",
            "marketplace_url",
            "cloud_registry",
            "registry_url",
        ):
            value = templates.get(setting)
            if value not in (None, "", False):
                findings.append(
                    {
                        "path": relative,
                        "setting": f"templates.{setting}",
                        "value": value,
                    }
                )
    return findings


def _remote_template_catalog_value(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"", "bundled", "local"}:
        return False
    return (
        "://" in lowered
        or lowered.startswith("remote")
        or "marketplace" in lowered
        or "cloud" in lowered
        or "registry" in lowered
    )


def _retrieval_evidence(project_root: Path) -> dict[str, Any]:
    return {
        "scorecard": _retrieval_scorecard_evidence(project_root),
        "demo": _retrieval_demo_evidence(project_root),
        "configuration": _retrieval_configuration_evidence(project_root),
    }


def _operator_evidence(project_root: Path) -> dict[str, Any]:
    return {
        "app_factory": _operator_app_factory_evidence(project_root),
        "api_smoke": _operator_api_smoke_evidence(project_root),
        "token_required": _operator_token_required_evidence(project_root),
        "host_rejection": _operator_host_rejection_evidence(project_root),
        "approval_binding": _operator_approval_binding_evidence(),
        "static_ui": _operator_static_ui_evidence(project_root),
    }


def _operator_app_factory_evidence(project_root: Path) -> dict[str, Any]:
    try:
        from agent_harness.operator import create_operator_app

        create_operator_app(project_root=project_root, token="readiness-token", profile="default")
    except Exception as exc:
        action = "Install agent-harness[operator] and ensure the operator app factory imports."
        return {
            "command": "import agent_harness.operator.create_operator_app",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": action,
        }
    return {
        "command": "import agent_harness.operator.create_operator_app",
        "status": "passed",
        "action": "Keep the operator app factory importable with operator extras installed.",
    }


def _operator_api_smoke_evidence(project_root: Path) -> dict[str, Any]:
    try:
        from fastapi.testclient import TestClient

        from agent_harness.operator import create_operator_app

        response = TestClient(
            create_operator_app(
                project_root=project_root,
                token="readiness-token",
                profile="default",
            )
        ).get("/health")
        payload = response.json()
    except Exception as exc:
        return {
            "command": "GET /health",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": "Install operator test dependencies and verify GET /health.",
        }
    status = (
        "passed"
        if response.status_code == 200 and payload.get("schema_version") == "operator_health.v1"
        else "failed"
    )
    return {
        "command": "GET /health",
        "status": status,
        "schema_version": payload.get("schema_version"),
        "action": "Verify the local operator health route before release.",
    }


def _operator_token_required_evidence(project_root: Path) -> dict[str, Any]:
    token = "readiness-token"
    try:
        from fastapi.testclient import TestClient

        from agent_harness.operator import create_operator_app

        response = TestClient(
            create_operator_app(project_root=project_root, token=token, profile="default")
        ).get("/api/v1/runs")
    except Exception as exc:
        return {
            "command": "GET /api/v1/runs without token",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": "Verify /api/v1 routes reject missing operator tokens.",
        }
    status = "passed" if response.status_code == 401 and token not in response.text else "failed"
    return {
        "command": "GET /api/v1/runs without token",
        "status": status,
        "status_code": response.status_code,
        "action": "Keep all /api/v1 operator routes token-protected.",
    }


def _operator_host_rejection_evidence(project_root: Path) -> dict[str, Any]:
    token = "readiness-token"
    command = [
        sys.executable,
        "-m",
        "agent_harness",
        "serve",
        "--host",
        "0.0.0.0",
        "--token",
        token,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return {
            "command": "python -m agent_harness serve --host 0.0.0.0",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": "Verify serve rejects non-loopback hosts before startup.",
        }
    combined_output = f"{result.stdout}\n{result.stderr}"
    status = (
        "passed"
        if result.returncode != 0 and "loopback" in combined_output and token not in combined_output
        else "failed"
    )
    return {
        "command": "python -m agent_harness serve --host 0.0.0.0",
        "status": status,
        "returncode": result.returncode,
        "action": "Keep the operator server loopback-only.",
    }


def _operator_approval_binding_evidence() -> dict[str, Any]:
    try:
        from fastapi.testclient import TestClient

        from agent_harness.core.runtime import HarnessRuntime
        from agent_harness.operator import create_operator_app
    except Exception as exc:
        return {
            "command": "operator approval binding smoke",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": "Install operator dependencies and verify approval binding enforcement.",
        }

    root = Path(tempfile.mkdtemp(prefix="operator-approval-binding-"))
    _write_operator_smoke_project(root)
    task_path = _write_operator_smoke_task(root)
    try:
        summary = HarnessRuntime(root).run_task(task_path)
        action_id = summary.approvals[0]
        run_dir = root / ".agent-harness" / "runs" / summary.run_id
        action_path = run_dir / "actions" / f"{action_id}.json"
        action = json.loads(action_path.read_text(encoding="utf-8"))
        action["call"]["arguments"]["proposed_content"] = "tampered\n"
        action_path.write_text(json.dumps(action), encoding="utf-8")
        response = TestClient(
            create_operator_app(
                project_root=root,
                token="readiness-token",
                profile="default",
            )
        ).post(
            f"/api/v1/runs/{summary.run_id}/approvals/{action_id}/decision",
            headers={"X-Agent-Harness-Operator-Token": "readiness-token"},
            json={"decision": "approve", "actor": "release-readiness"},
        )
        approval = json.loads(
            (run_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8")
        )
    except Exception as exc:
        return {
            "command": "operator approval binding smoke",
            "status": "failed",
            "detail": _safe_error(exc),
            "action": "Verify operator approval decisions cannot bypass binding checks.",
        }
    status = (
        "passed"
        if response.status_code == 422
        and "approval binding" in response.text
        and approval.get("status") == "pending"
        else "failed"
    )
    return {
        "command": "operator approval binding smoke",
        "status": status,
        "status_code": response.status_code,
        "action": "Keep operator approval decisions routed through approval binding checks.",
    }


def _write_operator_smoke_project(root: Path) -> None:
    (root / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v1",
                "project_name: operator-release-smoke",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def _write_operator_smoke_task(root: Path) -> Path:
    (root / "fixture.py").write_text(
        "def add_numbers(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "operator-release-smoke",
                "title": "Refactor",
                "intent": "Refactor add_numbers",
                "target_paths": ["fixture.py"],
                "allowed_tools": ["read_file", "patch_file"],
                "max_steps": 4,
            }
        ),
        encoding="utf-8",
    )
    return task_path


def _operator_static_ui_evidence(project_root: Path) -> dict[str, Any]:
    missing_package_data = _missing_operator_static_package_data(project_root)
    missing_assets: list[str] = []
    remote_markers: list[dict[str, str]] = []
    try:
        static_files = resources.files("agent_harness.operator.static")
        for asset in OPERATOR_STATIC_ASSETS:
            asset_path = static_files.joinpath(asset)
            if not asset_path.is_file():
                missing_assets.append(asset)
                continue
            text = asset_path.read_text(encoding="utf-8")
            for marker in OPERATOR_FORBIDDEN_REMOTE_MARKERS:
                if marker.lower() in text.lower():
                    remote_markers.append({"asset": asset, "marker": marker})
    except Exception as exc:
        return {
            "status": "failed",
            "missing_package_data": missing_package_data,
            "missing_assets": OPERATOR_STATIC_ASSETS,
            "remote_markers": [],
            "detail": _safe_error(exc),
            "action": "Package local operator UI assets with no external references.",
        }
    status = (
        "passed"
        if not missing_package_data and not missing_assets and not remote_markers
        else "missing_evidence"
    )
    if remote_markers:
        status = "failed"
    return {
        "status": status,
        "package_data": OPERATOR_STATIC_PACKAGE_DATA,
        "missing_package_data": missing_package_data,
        "missing_assets": missing_assets,
        "remote_markers": remote_markers,
        "action": "Package local operator UI assets and keep them free of external references.",
    }


def _missing_operator_static_package_data(project_root: Path) -> list[str]:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return list(OPERATOR_STATIC_PACKAGE_DATA)
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return list(OPERATOR_STATIC_PACKAGE_DATA)
    package_data = (
        data.get("tool", {}).get("setuptools", {}).get("package-data", {}).get("agent_harness", [])
    )
    if not isinstance(package_data, list):
        return list(OPERATOR_STATIC_PACKAGE_DATA)
    return [entry for entry in OPERATOR_STATIC_PACKAGE_DATA if entry not in package_data]


def _safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _retrieval_scorecard_evidence(project_root: Path) -> dict[str, Any]:
    scorecard_root = project_root / ".agent-harness" / "retrieval-scorecards"
    scorecard_paths = sorted(scorecard_root.glob("*.json")) if scorecard_root.exists() else []
    for path in scorecard_paths:
        relative = _project_relative(project_root, path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("schema_version") == "retrieval_scorecard.v1"
            and payload.get("status") == "passed"
        ):
            return {
                "command": "agent-harness retrieval scorecard <fixture> --index-id <index-id>",
                "status": "passed",
                "schema_version": "retrieval_scorecard.v1",
                "index_id": str(payload.get("index_id") or ""),
                "evidence": relative,
                "action": "Keep at least one passing retrieval scorecard before release.",
            }
    return {
        "command": "agent-harness retrieval scorecard <fixture> --index-id <index-id>",
        "status": "missing_evidence",
        "schema_version": "retrieval_scorecard.v1",
        "evidence": None,
        "checked_paths": [_project_relative(project_root, path) for path in scorecard_paths],
        "action": (
            "Run a local retrieval scorecard and keep the passing artifact under "
            ".agent-harness/retrieval-scorecards/."
        ),
    }


def _retrieval_demo_evidence(project_root: Path) -> dict[str, Any]:
    demo_root = project_root / "examples" / "retrieval_quality"
    required_files = [
        "README.md",
        "config.v2.yaml",
        "policy.v2.yaml",
        "scorecard.yaml",
        "task.json",
        "expected/retrieval_index.json",
        "expected/retrieval_scorecard.json",
    ]
    required_doc_names = {
        "architecture.md",
        "coding-rules.md",
        "public-notes.md",
        "semantic-note.md",
        "denied-internal.md",
        "secret-internal.md",
    }
    missing_files = [relative for relative in required_files if not (demo_root / relative).exists()]
    doc_names = (
        {path.name for path in (demo_root / "docs").rglob("*.md")}
        if (demo_root / "docs").exists()
        else set()
    )
    missing_docs = sorted(required_doc_names - doc_names)
    status = (
        "passed"
        if demo_root.exists() and not missing_files and not missing_docs
        else "missing_evidence"
    )
    return {
        "path": "examples/retrieval_quality",
        "status": status,
        "missing_files": missing_files,
        "missing_docs": missing_docs,
        "action": (
            "Add the retrieval quality demo README, local config, policy, documents, "
            "scorecard fixture, task, and expected artifact examples."
        ),
    }


def _retrieval_configuration_evidence(project_root: Path) -> dict[str, Any]:
    config_paths = _retrieval_config_paths(project_root)
    remote_defaults: list[dict[str, object]] = []
    for path in config_paths:
        try:
            config = load_mapping(path)
        except Exception as exc:
            remote_defaults.append(
                {
                    "path": _project_relative(project_root, path),
                    "setting": "parse_error",
                    "value": str(exc),
                }
            )
            continue
        remote_defaults.extend(_remote_retrieval_defaults(project_root, path, config))
    return {
        "status": "failed" if remote_defaults else "passed",
        "checked_paths": [_project_relative(project_root, path) for path in config_paths],
        "remote_defaults": remote_defaults,
        "action": (
            "Remove remote embeddings, hosted embedding providers, API-key-backed "
            "Qdrant, cloud Qdrant, HTTPS Qdrant, or non-loopback Qdrant defaults "
            "from executable configs."
        ),
    }


def _retrieval_config_paths(project_root: Path) -> list[Path]:
    paths: list[Path] = []
    root_config = project_root / "agent-harness.yaml"
    if root_config.exists():
        paths.append(root_config)
    examples = project_root / "examples"
    if examples.exists():
        paths.extend(sorted(examples.rglob("agent-harness.yaml")))
        paths.extend(sorted(examples.rglob("config.v2.yaml")))
    return sorted(dict.fromkeys(paths))


def _remote_retrieval_defaults(
    project_root: Path,
    path: Path,
    config: dict[str, Any],
) -> list[dict[str, object]]:
    retrieval = config.get("retrieval")
    if not isinstance(retrieval, dict):
        return []
    relative = _project_relative(project_root, path)
    findings: list[dict[str, object]] = []
    dense = retrieval.get("dense")
    if isinstance(dense, dict):
        if dense.get("remote_embeddings") is True:
            findings.append(
                {
                    "path": relative,
                    "setting": "retrieval.dense.remote_embeddings",
                    "value": True,
                }
            )
        provider = dense.get("embedding_provider")
        if provider not in {None, "deterministic", "fastembed"}:
            findings.append(
                {
                    "path": relative,
                    "setting": "retrieval.dense.embedding_provider",
                    "value": str(provider),
                }
            )
    qdrant = retrieval.get("qdrant")
    if isinstance(qdrant, dict):
        if qdrant.get("api_key_env") is not None:
            findings.append(
                {
                    "path": relative,
                    "setting": "retrieval.qdrant.api_key_env",
                    "value": str(qdrant["api_key_env"]),
                }
            )
        url = qdrant.get("url")
        if isinstance(url, str) and _remote_qdrant_url(url):
            findings.append(
                {
                    "path": relative,
                    "setting": "retrieval.qdrant.url",
                    "value": url,
                }
            )
    return findings


def _remote_qdrant_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme.lower() == "https":
        return True
    if hostname.endswith("cloud.qdrant.io"):
        return True
    if hostname == "localhost":
        return False
    try:
        return not ip_address(hostname).is_loopback
    except ValueError:
        return bool(hostname)


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


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return {
            "command": " ".join(command),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
            "status": "failed",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "command timed out",
            "status": "failed",
        }
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "status": "passed" if result.returncode == 0 else "failed",
    }


def _skipped_result(reason: str) -> dict[str, Any]:
    return {
        "command": "",
        "returncode": None,
        "stdout": "",
        "stderr": reason,
        "status": "failed",
    }


def _write_release_evidence(
    project_root: Path,
    name: str,
    payload: dict[str, Any],
) -> None:
    write_json(project_root / RELEASE_EVIDENCE_DIR / f"{name}.json", payload)


def _venv_python(venv_path: Path) -> Path:
    if _is_windows():
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _console_script(venv_path: Path) -> Path:
    if _is_windows():
        return venv_path / "Scripts" / "agent-harness.exe"
    return venv_path / "bin" / "agent-harness"


def _is_windows() -> bool:
    return os.name == "nt"


def _artifact_record(project_root: Path, path: Path | None) -> dict[str, str | None]:
    if path is None or not path.exists():
        return {
            "path": None,
            "sha256": None,
        }
    return {
        "path": _project_relative(project_root, path),
        "sha256": hash_file(path),
    }


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _release_evidence(project_root: Path, name: str) -> dict[str, str]:
    relative = RELEASE_EVIDENCE_DIR / f"{name}.json"
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
    retrieval: dict[str, Any],
    operator: dict[str, Any],
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
    _collect_status_diagnostics(diagnostics, "retrieval", retrieval)
    _collect_status_diagnostics(diagnostics, "operator", operator)
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
