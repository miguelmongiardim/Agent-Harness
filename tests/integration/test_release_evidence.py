from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from agent_harness import __version__, release
from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from tests.conftest import seed_project

pytestmark = [pytest.mark.slow, pytest.mark.release_gate]


def test_release_readiness_report_requires_docs_checks_ci_advisories_and_changelog(
    capsys: pytest.CaptureFixture[str],
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


def test_release_readiness_defaults_to_project_version_and_reports_missing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "0.3.0")

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["version"] == "0.3.0"
    assert report["status"] == "pending"

    assert report["package"]["build"]["command"] == "python -m build"
    assert report["package"]["clean_install"]["command"].startswith("python -m pip install")
    assert report["package"]["console_script"]["command"] == "agent-harness doctor"

    assert report["demos"]["provider-audit"]["command"] == "agent-harness demo provider-audit"
    assert report["demos"]["python-refactor"]["command"].startswith("agent-harness run")

    assert report["docs"]["check"]["status"] in {"passed", "failed"}
    assert (
        report["docs"]["schema_compatibility"]["path"]
        == "docs/prd-agent-harness-v1.0.0-mature-cli-runtime.md"
    )
    assert report["docs"]["schema_compatibility"]["present"] is True
    assert report["docs"]["roadmap_claims"]["status"] in {"passed", "failed"}

    assert report["templates"]["validation"]["command"] == "agent-harness template validate --all"
    assert report["release_artifacts"]["wheel"]["expected_glob"] == (
        "dist/agent_harness-0.3.0-*.whl"
    )
    assert report["release_artifacts"]["sdist"]["expected_glob"] == (
        "dist/agent_harness-0.3.0.tar.gz"
    )

    missing = [entry for entry in report["diagnostics"] if entry["status"] != "passed"]
    assert missing
    assert all(entry["action"] for entry in missing)


def test_release_readiness_reports_operator_evidence_and_requires_packaged_ui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "1.3.0")

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    operator = report["operator"]
    assert operator["app_factory"]["status"] == "passed"
    assert operator["api_smoke"]["status"] == "passed"
    assert operator["token_required"]["status"] == "passed"
    assert operator["host_rejection"]["status"] == "passed"
    assert operator["approval_binding"]["status"] == "passed"
    assert operator["static_ui"]["status"] == "missing_evidence"
    assert operator["static_ui"]["missing_package_data"] == [
        "operator/static/*.html",
        "operator/static/*.css",
        "operator/static/*.js",
    ]
    assert operator["static_ui"]["remote_markers"] == []
    assert "operator.static_ui" in {entry["gate"] for entry in report["diagnostics"]}


def test_release_readiness_reports_ready_when_required_evidence_is_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(
        release,
        "_remote_ci_evidence",
        lambda project_root, target_commit, ci_run_id: {
            "run": {
                "source": "github_actions",
                "status": "completed",
                "conclusion": "success",
                "matches_target_commit": True,
            },
            "python_3_11": {"required": True, "status": "passed"},
            "python_3_12": {"required": True, "status": "passed"},
            "python_3_13": {"allowed_failure": True, "status": "failed_allowed"},
        },
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["version"] == "9.9.9"
    assert report["status"] == "ready", report["mcp"]["stdio_protocol"]
    assert report["diagnostics"] == []
    assert report["package"]["build"]["status"] == "passed"
    assert report["package"]["clean_install"]["status"] == "passed"
    assert report["package"]["console_script"]["status"] == "passed"
    assert report["demos"]["provider-audit"]["status"] == "passed"
    assert report["templates"]["validation"]["status"] == "passed"
    assert all(entry["status"] == "passed" for entry in report["operator"].values())


def test_release_readiness_runs_v140_bundled_template_pack_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(
        release,
        "_remote_ci_evidence",
        lambda project_root, target_commit, ci_run_id: {
            "run": {
                "source": "github_actions",
                "status": "completed",
                "conclusion": "success",
                "matches_target_commit": True,
            },
            "python_3_11": {"required": True, "status": "passed"},
            "python_3_12": {"required": True, "status": "passed"},
            "python_3_13": {"allowed_failure": True, "status": "failed_allowed"},
        },
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "ready", report["diagnostics"]
    templates = report["templates"]
    assert templates["bundled_pack_acceptance"]["status"] == "passed"
    assert templates["bundled_pack_acceptance"]["template_ids"] == [
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    ]
    assert templates["remote_catalog_defaults"]["status"] == "passed"
    assert templates["remote_catalog_defaults"]["remote_defaults"] == []

    for pack in templates["bundled_pack_acceptance"]["packs"]:
        assert pack["validation"]["status"] == "passed"
        assert pack["dry_run"]["status"] == "passed"
        assert pack["clean_apply"]["status"] == "passed"
        assert pack["generated_examples"]["status"] == "passed"
        assert pack["application_evidence"]["status"] == "passed"
        assert pack["docs"]["status"] == "passed"


def test_release_readiness_requires_v150_skills_workflow_demo_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9", include_skills=False)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    assert report["skills"]["workflow_demo"]["status"] == "missing_evidence"
    assert "skills.workflow_demo" in {entry["gate"] for entry in report["diagnostics"]}


def test_release_readiness_verifies_v150_skill_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "ready", report["diagnostics"]
    assert report["diagnostics"] == []
    skills = report["skills"]
    assert skills["bundled_validation"]["status"] == "passed"
    assert set(skills["bundled_validation"]["skill_ids"]) == {
        "write-a-prd",
        "prd-to-plan",
        "tdd",
        "prd-plan-tdd-workflow",
    }
    assert skills["registry_commands"]["status"] == "passed"
    assert skills["workflow_demo"]["status"] == "passed"
    assert skills["workflow_demo"]["resolution"]["status"] == "passed"
    assert skills["workflow_demo"]["dry_run"]["status"] == "passed"
    assert skills["workflow_demo"]["context_manifest"]["status"] == "passed"
    assert skills["workflow_demo"]["skill_manifest"]["status"] == "passed"
    assert skills["workflow_demo"]["inspect"]["status"] == "passed"
    assert skills["docs"]["status"] == "passed"


def test_release_readiness_requires_v160_mcp_boundary_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9", include_mcp=False)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    assert report["mcp"]["demo"]["status"] == "missing_evidence"
    assert report["mcp"]["extra_install"]["status"] == "missing_evidence"
    assert report["mcp"]["ci_install"]["status"] == "missing_evidence"
    assert {"mcp.demo", "mcp.extra_install", "mcp.ci_install"} <= {
        entry["gate"] for entry in report["diagnostics"]
    }


def test_release_readiness_requires_v170_orchestration_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9", include_orchestration=False)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    assert report["orchestration"]["demo"]["status"] == "missing_evidence"
    assert "orchestration.demo" in {entry["gate"] for entry in report["diagnostics"]}


def test_release_readiness_verifies_v170_orchestration_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9", include_orchestration=False)
    _write_inline_orchestration_workflow_demo(tmp_path)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "ready", report["diagnostics"]
    orchestration = report["orchestration"]
    assert orchestration["demo"]["status"] == "passed"
    assert orchestration["policy_gates"]["status"] == "passed"
    assert orchestration["policy_gates"]["roles"] == [
        "planner",
        "implementer",
        "reviewer",
        "tester",
    ]
    assert orchestration["artifact_checks"]["status"] == "passed"
    assert orchestration["artifact_checks"]["handoff_count"] == 3
    assert orchestration["inspect_export"]["status"] == "passed"
    assert orchestration["mcp_resource_reads"]["status"] == "passed"
    assert orchestration["mcp_access_log"]["status"] == "passed"


def test_release_readiness_requires_existing_evidence_pack_without_generating_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9", include_evidence_pack=False)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    evidence_root = tmp_path / ".agent-harness" / "evidence"
    assert not evidence_root.exists()

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    assert report["evidence_pack"]["status"] == "missing_evidence"
    assert report["evidence_pack"]["command"] == "agent-harness evidence pack"
    assert "evidence_pack" in {entry["gate"] for entry in report["diagnostics"]}
    assert not (evidence_root / "evidence_pack.v1.json").exists()


def test_release_readiness_validates_pack_links_and_blocks_critical_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(
        tmp_path,
        "9.9.9",
        evidence_findings=[
            {
                "schema_version": "evidence_finding.v1",
                "finding_id": "critical-unsafe-release-finding",
                "severity": "critical",
                "domain": "evidence",
                "source": "raw_provider_payload",
                "message": "raw provider prompt with sk-release-secret must not appear",
                "artifact_reference": "C:/Users/example/raw-provider-payload.json",
                "evidence_refs": ["C:/Users/example/raw-provider-payload.json"],
                "omission_reason": "raw_provider_payload",
                "recommendation": "Keep only redacted provider evidence.",
                "blocks_release": True,
                "blocks_evidence_pack": True,
            },
            {
                "schema_version": "evidence_finding.v1",
                "finding_id": "advisory-release-finding",
                "severity": "low",
                "domain": "docs_claim",
                "source": "docs_claim_review",
                "message": "advisory finding remains visible",
                "artifact_reference": ".agent-harness/evidence/evidence_pack.v1.json",
                "evidence_refs": [".agent-harness/evidence/evidence_pack.v1.json"],
                "omission_reason": None,
                "recommendation": "Review before release.",
                "blocks_release": False,
                "blocks_evidence_pack": False,
            },
        ],
    )
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    evidence_pack = report["evidence_pack"]
    assert evidence_pack["status"] == "failed"
    assert evidence_pack["current_pack"]["pack_id"] == "release-ready-evidence-pack"
    assert evidence_pack["artifacts"] == {
        "evidence_pack": ".agent-harness/evidence/evidence_pack.v1.json",
        "manifest": ".agent-harness/evidence/evidence_manifest.v1.json",
        "artifact_index": ".agent-harness/evidence/evidence_index.v1.json",
        "findings": ".agent-harness/evidence/evidence_findings.v1.json",
        "control_mapping": ".agent-harness/evidence/control_mapping.v1.json",
        "checksums": ".agent-harness/evidence/checksums.sha256",
    }
    assert evidence_pack["validation"]["checksums"] == "passed"
    assert evidence_pack["findings"]["critical"] == 1
    assert evidence_pack["findings"]["advisory"] == 1
    assert evidence_pack["findings"]["blocking"] == 1
    assert evidence_pack["findings"]["blocking_findings"] == [
        {
            "finding_id": "critical-unsafe-release-finding",
            "severity": "critical",
            "domain": "evidence",
            "source": "raw_provider_payload",
            "omission_reason": "raw_provider_payload",
            "blocks_release": True,
            "blocks_evidence_pack": True,
            "evidence_refs": [],
        }
    ]
    assert evidence_pack["findings"]["advisory_findings"] == [
        {
            "finding_id": "advisory-release-finding",
            "severity": "low",
            "domain": "docs_claim",
            "source": "docs_claim_review",
            "omission_reason": None,
            "blocks_release": False,
            "blocks_evidence_pack": False,
            "evidence_refs": [".agent-harness/evidence/evidence_pack.v1.json"],
        }
    ]
    assert "evidence_pack.findings" in {entry["gate"] for entry in report["diagnostics"]}
    serialized = json.dumps(report)
    assert "sk-release-secret" not in serialized
    assert "raw provider prompt" not in serialized
    assert "C:/Users/example" not in serialized


def test_release_readiness_verifies_v160_mcp_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    _write_mcp_boundary_demo(tmp_path)
    _write_mcp_ci_workflow(tmp_path)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(release, "_remote_ci_evidence", _passing_remote_ci)

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "ready", report["mcp"]["stdio_protocol"]
    assert report["diagnostics"] == []
    mcp = report["mcp"]
    assert mcp["demo"]["status"] == "passed"
    assert mcp["extra_install"]["status"] == "passed"
    assert mcp["ci_install"]["status"] == "passed"
    assert mcp["cli_commands"]["status"] == "passed"
    assert mcp["resource_listing"]["status"] == "passed"
    assert mcp["resource_reads"]["status"] == "passed"
    assert mcp["prompt_commands"]["status"] == "passed"
    assert mcp["denied_resource"]["status"] == "passed"
    assert mcp["access_log"]["status"] == "passed"
    assert mcp["stdio_protocol"]["status"] == "passed"
    assert mcp["stdio_protocol"]["resources_advertised"] is True
    assert mcp["stdio_protocol"]["prompts_advertised"] is True
    assert mcp["stdio_protocol"]["tools_advertised"] is False


def test_v140_template_pack_golden_path_example_and_cli_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "examples" / "template_pack_system" / "README.md"
    text = readme.read_text(encoding="utf-8")

    for command in (
        "agent-harness template list",
        "agent-harness template show python-lib",
        "agent-harness template validate python-lib",
        "agent-harness template apply python-lib --target ./scratch/python-lib --dry-run",
        "agent-harness template apply python-lib --target ./scratch/python-lib --preview-diff",
        "agent-harness template apply python-lib --target ./scratch/python-lib",
        "agent-harness release readiness",
    ):
        assert command in text

    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["template", "list"]) == 0
    listed = capsys.readouterr().out
    assert "python-lib" in listed
    assert "bundled_pack" in listed

    assert main(["template", "show", "python-lib"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["template_id"] == "python-lib"
    assert shown["source_type"] == "bundled_pack"

    assert main(["template", "validate", "python-lib"]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "passed"

    target = tmp_path / "scratch" / "python-lib"
    assert main(["template", "apply", "python-lib", "--target", str(target), "--dry-run"]) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert dry_run["status"] == "planned"
    assert not (target / "pyproject.toml").exists()

    assert main(["template", "apply", "python-lib", "--target", str(target), "--preview-diff"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["mode"] == "preview_diff"
    assert preview["preview_diffs"]
    assert not (target / "pyproject.toml").exists()

    assert main(["template", "apply", "python-lib", "--target", str(target)]) == 0
    apply_summary = json.loads(capsys.readouterr().out)
    assert apply_summary["status"] == "completed"
    assert (target / "pyproject.toml").exists()

    assert main(["release", "readiness", "--version", "9.9.9"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["templates"]["bundled_pack_acceptance"]["status"] == "passed"
    assert readiness["templates"]["remote_catalog_defaults"]["status"] == "passed"


def test_v150_skills_workflow_golden_path_example_and_cli_sequence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "examples" / "skills_workflow" / "README.md"
    text = readme.read_text(encoding="utf-8")

    for command in (
        "uv sync",
        "uv run agent-harness skill list",
        "uv run agent-harness skill show prd-plan-tdd-workflow",
        "uv run agent-harness skill validate prd-plan-tdd-workflow",
        "uv run agent-harness skill resolve --task examples/skills_workflow/task.yaml",
        "uv run agent-harness run examples/skills_workflow/task.yaml --dry-run",
        "uv run agent-harness inspect run <run-id>",
        "uv run agent-harness release readiness",
    ):
        assert command in text

    monkeypatch.chdir(repo_root)
    task_path = repo_root / "examples" / "skills_workflow" / "task.yaml"

    assert main(["skill", "list"]) == 0
    listed = capsys.readouterr().out
    assert "prd-plan-tdd-workflow" in listed

    assert main(["skill", "show", "prd-plan-tdd-workflow"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["skill_id"] == "prd-plan-tdd-workflow"
    assert shown["validation_status"] == "passed"

    assert main(["skill", "validate", "prd-plan-tdd-workflow"]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "passed"

    assert main(["skill", "resolve", "--task", str(task_path)]) == 0
    resolution = json.loads(capsys.readouterr().out)
    assert resolution["status"] == "passed"
    assert resolution["skills"][0]["skill_id"] == "prd-plan-tdd-workflow"

    assert main(["run", str(task_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "dry_run"
    assert summary["artifacts"]["skill_manifest"].endswith("skill_manifest.json")
    run_dir = repo_root / ".agent-harness" / "runs" / summary["run_id"]
    skill_manifest = json.loads((run_dir / "skill_manifest.json").read_text(encoding="utf-8"))
    assert skill_manifest["skills"][0]["skill_id"] == "prd-plan-tdd-workflow"
    assert skill_manifest["skills"][0]["inclusion_status"] == "included"

    assert main(["inspect", "run", summary["run_id"]]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["skill_manifest"] == skill_manifest


def test_v160_mcp_boundary_golden_path_example_and_cli_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "examples" / "mcp_boundary" / "README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")

    for command in (
        "uv sync --extra mcp",
        "uv run agent-harness demo provider-audit",
        "uv run agent-harness mcp resources list --json",
        "uv run agent-harness mcp resources read agent-harness://runs/<run-id>/summary --json",
        "uv run agent-harness mcp resources read agent-harness://runs/<run-id>/context --json",
        "uv run agent-harness mcp prompts list --json",
        (
            "uv run agent-harness mcp prompts get agent-harness-run-review "
            "--arg run_id=<run-id> --json"
        ),
        "uv run agent-harness mcp serve",
        "uv run agent-harness release readiness",
    ):
        assert command in text

    expected_root = repo_root / "examples" / "mcp_boundary" / "expected"
    expected_resources = json.loads((expected_root / "resources-list.json").read_text())
    expected_prompts = json.loads((expected_root / "prompts-list.json").read_text())
    expected_denial = json.loads((expected_root / "denied-resource.json").read_text())
    assert expected_resources["schema_version"] == "mcp_resource_list.v1"
    assert expected_prompts["schema_version"] == "mcp_prompt_list.v1"
    assert expected_denial["schema_version"] == "mcp_resource_envelope.v1"
    assert expected_denial["denial_status"] == "denied"

    source = repo_root / "examples" / "provider_audit"
    workspace = tmp_path / "examples" / "provider_audit"
    shutil.copytree(source, workspace, ignore=shutil.ignore_patterns(".agent-harness"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-mcp-boundary-demo")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-29T15:30:00Z")

    assert main(["demo", "provider-audit"]) == 0
    demo = json.loads(capsys.readouterr().out)
    run_id = demo["run_id"]
    monkeypatch.chdir(workspace)

    assert main(["mcp", "resources", "list", "--json"]) == 0
    resources = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in resources["resources"]}
    assert resources["schema_version"] == "mcp_resource_list.v1"
    assert f"agent-harness://runs/{run_id}/summary" in resource_uris
    assert f"agent-harness://runs/{run_id}/context" in resource_uris

    assert (
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/summary", "--json"]) == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["denial_status"] == "allowed"
    assert summary["content"]["run_id"] == run_id

    assert (
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/context", "--json"]) == 0
    )
    context = json.loads(capsys.readouterr().out)
    assert context["denial_status"] == "allowed"
    assert context["resource_type"] == "run_context"

    assert main(["mcp", "prompts", "list", "--json"]) == 0
    prompts = json.loads(capsys.readouterr().out)
    assert "agent-harness-run-review" in {prompt["name"] for prompt in prompts["prompts"]}

    assert (
        main(
            [
                "mcp",
                "prompts",
                "get",
                "agent-harness-run-review",
                "--arg",
                f"run_id={run_id}",
                "--json",
            ]
        )
        == 0
    )
    prompt = json.loads(capsys.readouterr().out)
    assert prompt["denial_status"] == "allowed"
    assert f"agent-harness://runs/{run_id}/summary" in prompt["resource_references"]

    assert main(["mcp", "resources", "read", "file:///tmp/secret.txt", "--json"]) == 1
    denied = json.loads(capsys.readouterr().out)
    assert denied["denial_status"] == "denied"
    assert denied["metadata"]["denial_reason"] == "unsupported_uri_scheme"

    records = [
        json.loads(line)
        for line in (workspace / ".agent-harness" / "mcp" / "access-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {(record["request_type"], record["result"]) for record in records} >= {
        ("resource_read", "allowed"),
        ("resource_read", "denied"),
        ("prompt_list", "allowed"),
        ("prompt_get", "allowed"),
    }


def test_v170_orchestration_workflow_golden_path_example_and_cli_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "examples" / "orchestration_workflow" / "README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")

    for command in (
        "uv run agent-harness orchestration run orchestration.json --dry-run",
        "uv run agent-harness orchestration inspect workflow-demo",
        "uv run agent-harness orchestration export workflow-demo",
        "uv run agent-harness mcp resources list --json",
        (
            "uv run agent-harness mcp resources read "
            "agent-harness://orchestrations/workflow-demo/summary --json"
        ),
        (
            "uv run agent-harness mcp resources read "
            "agent-harness://orchestrations/workflow-demo/handoffs --json"
        ),
        "uv run agent-harness release readiness --version 1.9.0",
    ):
        assert command in text

    source = repo_root / "examples" / "orchestration_workflow"
    workspace = tmp_path / "examples" / "orchestration_workflow"
    shutil.copytree(source, workspace, ignore=shutil.ignore_patterns(".agent-harness"))
    monkeypatch.chdir(workspace)

    assert main(["orchestration", "run", "orchestration.json", "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_version"] == "orchestration_summary.v1"
    assert summary["orchestration_id"] == "workflow-demo"
    assert summary["status"] == "dry_run"
    assert [child["role"] for child in summary["children"]] == [
        "planner",
        "implementer",
        "reviewer",
        "tester",
    ]

    assert main(["orchestration", "inspect", "workflow-demo"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["schema_version"] == "orchestration_inspection.v1"
    assert len(inspected["handoffs"]) == 3

    assert main(["orchestration", "export", "workflow-demo"]) == 0
    export_path = Path(capsys.readouterr().out.strip())
    exported = json.loads((workspace / export_path).read_text(encoding="utf-8"))
    assert exported["schema_version"] == "orchestration_export.v1"
    assert exported["orchestration_id"] == "workflow-demo"

    assert main(["mcp", "resources", "list", "--json"]) == 0
    resources = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in resources["resources"]}
    assert "agent-harness://orchestrations/workflow-demo/summary" in resource_uris
    assert "agent-harness://orchestrations/workflow-demo/handoffs" in resource_uris

    assert (
        main(
            [
                "mcp",
                "resources",
                "read",
                "agent-harness://orchestrations/workflow-demo/summary",
                "--json",
            ]
        )
        == 0
    )
    summary_envelope = json.loads(capsys.readouterr().out)
    assert summary_envelope["denial_status"] == "allowed"
    assert summary_envelope["resource_type"] == "orchestration_summary"

    assert (
        main(
            [
                "mcp",
                "resources",
                "read",
                "agent-harness://orchestrations/workflow-demo/handoffs",
                "--json",
            ]
        )
        == 0
    )
    handoffs_envelope = json.loads(capsys.readouterr().out)
    assert handoffs_envelope["denial_status"] == "allowed"
    assert handoffs_envelope["resource_type"] == "orchestration_handoffs"

    records = [
        json.loads(line)
        for line in (workspace / ".agent-harness" / "mcp" / "access-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {
        record["artifact_type"]
        for record in records
        if record["orchestration_id"] == "workflow-demo"
    } >= {"orchestration_summary", "orchestration_handoffs"}
    assert all("content" not in record for record in records)


def test_release_readiness_rejects_remote_template_catalog_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_project_without_evidence(tmp_path, "1.3.0")
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: remote-template-default",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: https://templates.example.invalid/catalog.json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    remote_defaults = report["templates"]["remote_catalog_defaults"]
    assert remote_defaults["status"] == "failed"
    assert remote_defaults["remote_defaults"] == [
        {
            "path": "agent-harness.yaml",
            "setting": "template_catalog",
            "value": "https://templates.example.invalid/catalog.json",
        }
    ]
    assert "templates.remote_catalog_defaults" in {entry["gate"] for entry in report["diagnostics"]}


def test_release_readiness_requires_v100_release_closure_docs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "1.0.0")
    for path in (tmp_path / "docs" / "migration.md", tmp_path / "docs" / "release-readiness.md"):
        path.unlink(missing_ok=True)
    monkeypatch.setattr(release, "_tag_exists", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_pushed", lambda project_root, tag_name: True)
    monkeypatch.setattr(release, "_tag_target_commit", lambda project_root, tag_name: "abc123")
    monkeypatch.setattr(
        release,
        "_remote_ci_evidence",
        lambda project_root, target_commit, ci_run_id: {
            "run": {
                "source": "github_actions",
                "status": "completed",
                "conclusion": "success",
                "matches_target_commit": True,
            },
            "python_3_11": {"required": True, "status": "passed"},
            "python_3_12": {"required": True, "status": "passed"},
            "python_3_13": {"allowed_failure": True, "status": "failed_allowed"},
        },
    )

    assert main(["release", "readiness"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "pending"
    assert report["docs"]["migration_notes"]["status"] == "missing_evidence"
    assert report["docs"]["release_process"]["status"] == "missing_evidence"
    diagnostic_gates = {entry["gate"] for entry in report["diagnostics"]}
    assert {"docs.migration_notes", "docs.release_process"} <= diagnostic_gates


def test_current_release_metadata_and_v100_closure_docs_are_complete() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "1.9.0"
    assert __version__ == "1.9.0"

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [1.9.0]" in changelog
    assert "## [1.7.1]" in changelog
    assert "## [1.7.0]" in changelog
    assert "## [1.6.1]" in changelog
    assert "## [1.6.0]" in changelog
    assert "## [1.5.0]" in changelog
    assert "## [1.4.0]" in changelog
    assert "## [1.3.0]" in changelog
    assert "## [1.2.0]" in changelog
    assert "## [1.1.0]" in changelog
    assert "## [1.0.0]" in changelog

    migration = Path("docs/migration.md").read_text(encoding="utf-8")
    assert "v0.3.0" in migration
    assert "v1.0.0" in migration
    assert "public compatibility baseline" in migration

    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    for marker in ("Release Checklist", "Tag Process", "Artifact Verification"):
        assert marker in release_docs


def test_ci_installs_operator_extra_and_runs_operator_release_gates() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python -m pip install -e .[dev,operator,mcp]" in workflow
    assert "tests/integration/test_operator_cli.py" in workflow
    assert "tests/integration/test_operator_api.py" in workflow
    assert "tests/integration/test_operator_ui.py" in workflow
    assert "tests/integration/test_mcp_protocol.py" in workflow
    assert "tests/integration/test_orchestration_cli.py" in workflow
    assert "tests/integration/test_release_evidence.py" in workflow
    assert (
        "python -m agent_harness governance export --output .agent-harness/governance" in workflow
    )
    assert "python -m agent_harness evidence pack --output .agent-harness/evidence" in workflow


def test_operator_release_docs_cover_v130_golden_path_and_evidence() -> None:
    operator_docs = Path("docs/operator-ui.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{operator_docs}\n{release_docs}"

    assert "uv sync --extra operator" in combined
    assert "uv run agent-harness demo provider-audit" in combined
    assert "uv run agent-harness serve --host 127.0.0.1 --port 8765" in combined
    assert "operator.app_factory" in combined
    assert "operator.static_ui" in combined
    assert "operator.approval_binding" in combined
    assert "hosted API" in operator_docs
    assert "Roadmap / Not implemented yet" in operator_docs


def test_mcp_release_docs_cover_v160_golden_path_and_evidence() -> None:
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    mcp_example = Path("examples/mcp_boundary/README.md").read_text(encoding="utf-8")
    combined = f"{release_docs}\n{mcp_example}"

    assert "examples/mcp_boundary" in release_docs
    assert "uv sync --extra mcp" in combined
    assert "agent-harness mcp resources list --json" in combined
    assert "agent-harness mcp prompts get agent-harness-run-review" in combined
    assert "agent-harness mcp serve" in combined
    assert "mcp.extra_install" in release_docs
    assert "mcp.stdio_protocol" in release_docs
    assert "Planned v1.6.0 MCP Gates" not in release_docs


def test_orchestration_release_docs_cover_v170_golden_path_and_evidence() -> None:
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    orchestration_example = Path("examples/orchestration_workflow/README.md").read_text(
        encoding="utf-8"
    )
    combined = f"{release_docs}\n{orchestration_example}"

    assert "examples/orchestration_workflow" in release_docs
    assert "agent-harness orchestration run orchestration.json --dry-run" in combined
    assert "agent-harness orchestration inspect workflow-demo" in combined
    assert "agent-harness orchestration export workflow-demo" in combined
    assert (
        "agent-harness mcp resources read agent-harness://orchestrations/workflow-demo/summary"
    ) in combined
    assert "orchestration.policy_gates" in release_docs
    assert "orchestration.artifact_checks" in release_docs
    assert "orchestration.inspect_export" in release_docs
    assert "orchestration.mcp_resource_reads" in release_docs
    assert "orchestration.mcp_access_log" in release_docs
    assert "Parallel execution" in combined
    assert "hosted APIs" in combined
    assert "Planned v1.7.0" not in release_docs


def test_release_package_check_builds_installs_and_records_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")
    commands: list[list[str]] = []

    def fake_run_command(
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        del timeout_seconds
        commands.append(command)
        if command[1:3] == ["-m", "build"]:
            dist = cwd / "dist"
            dist.mkdir(exist_ok=True)
            (dist / "agent_harness-9.9.9-py3-none-any.whl").write_text("wheel", encoding="utf-8")
            (dist / "agent_harness-9.9.9.tar.gz").write_text("sdist", encoding="utf-8")
        return {
            "command": " ".join(command),
            "returncode": 0,
            "stdout": "ok",
            "stderr": "",
            "status": "passed",
        }

    monkeypatch.setattr(release, "_run_command", fake_run_command, raising=False)

    assert main(["release", "package-check"]) == 0
    package_report = json.loads(capsys.readouterr().out)

    assert package_report["schema_version"] == "release_package_check.v1"
    assert package_report["status"] == "passed"
    assert package_report["version"] == "9.9.9"
    assert package_report["artifacts"]["wheel"]["sha256"]
    assert package_report["artifacts"]["sdist"]["sha256"]
    assert any(command[1:5] == ["-m", "build", "--outdir", "dist"] for command in commands)
    assert any(command[1:3] == ["-m", "venv"] for command in commands)
    assert any(command[1:4] == ["-m", "pip", "install"] for command in commands)
    assert any(command[-1] == "doctor" and "agent-harness" in command[-2] for command in commands)

    evidence_dir = tmp_path / ".agent-harness" / "release" / "evidence"
    assert json.loads((evidence_dir / "package-build.json").read_text())["status"] == "passed"
    assert json.loads((evidence_dir / "clean-install.json").read_text())["status"] == "passed"
    assert json.loads((evidence_dir / "console-script.json").read_text())["status"] == "passed"

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["package"]["build"]["status"] == "passed"
    assert readiness["package"]["clean_install"]["status"] == "passed"
    assert readiness["package"]["console_script"]["status"] == "passed"


def test_packaging_docs_cover_uv_sync_and_package_install_paths() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{release_docs}"

    assert "uv sync --extra dev" in combined
    assert "python -m pip install ." in combined
    assert "agent-harness release package-check" in combined


def test_demo_docs_cover_provider_audit_and_secondary_python_refactor_paths() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    provider_demo = Path("examples/provider_audit/README.md").read_text(encoding="utf-8")
    release_docs = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{provider_demo}\n{release_docs}"

    assert "agent-harness demo provider-audit" in combined
    assert "agent-harness run examples/tasks/python_refactor.json --dry-run" in combined
    assert "demo-python-refactor.json" in combined


def test_template_validation_satisfies_release_readiness_template_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_release_ready_project(tmp_path, "9.9.9")

    assert main(["template", "validate", "--all"]) == 0
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["status"] == "passed"
    assert {entry["template_id"] for entry in evidence["templates"]} == {
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    }

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)
    assert readiness["templates"]["validation"]["status"] == "passed"
    assert readiness["templates"]["validation"]["evidence"] == (
        ".agent-harness/release/evidence/template-validation.json"
    )


def _write_release_ready_project(
    root: Path,
    version: str,
    *,
    include_skills: bool = True,
    include_mcp: bool = True,
    include_orchestration: bool = True,
    include_evidence_pack: bool = True,
    evidence_findings: list[dict[str, Any]] | None = None,
) -> None:
    if not (root / "agent-harness.yaml").exists():
        (root / "agent-harness.yaml").write_text(
            "\n".join(
                [
                    "schema_version: config.v1",
                    "project_name: release-ready",
                    "artifact_root: .agent-harness",
                    "default_policy: default",
                    "retrieval_backend: lexical",
                    "template_catalog: bundled",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    (root / "policies").mkdir(exist_ok=True)
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "agent-harness"',
                f'version = "{version}"',
                "",
                "[tool.setuptools.package-data]",
                "agent_harness = [",
                '  "operator/static/*.html",',
                '  "operator/static/*.css",',
                '  "operator/static/*.js",',
                "]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Agent Harness",
                "",
                "## What This Repo Proves",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## Roadmap / Not Enabled By Init",
                "",
                "Roadmap features remain future scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "prd-agent-harness-v1.0.0-mature-cli-runtime.md").write_text(
        "\n".join(
            [
                "# Agent Harness v1.0.0 / v1.0.0 PRD",
                "",
                "Agent Harness v1.0.0 is the v1.0.0 Mature CLI/runtime release.",
                "",
                "## Compatibility And Deprecation Policy",
                "",
                "v0.3.0 schemas are the v1.0.0 public baseline.",
                "",
                "## Implemented vs Roadmap",
                "",
                "Implemented capabilities are separate from roadmap scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (docs / "migration.md").write_text(
        "\n".join(
            [
                "# Schema Migration",
                "",
                "## Migration Notes From v0.3.0 To v1.0.0",
                "",
                "v1.0.0 keeps the v0.3.0 schemas as the public baseline.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (docs / "release-readiness.md").write_text(
        "\n".join(
            [
                "# Release Readiness",
                "",
                "## Release Checklist",
                "",
                "Run package, demo, template, docs, artifact, tag, and CI checks.",
                "",
                "## Tag Process",
                "",
                "Create and push the release tag only after final verification.",
                "",
                "## Artifact Verification",
                "",
                "Verify wheel and source distribution hashes before release.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-04-26\n\n- Release.\n",
        encoding="utf-8",
    )
    dist = root / "dist"
    dist.mkdir()
    (dist / f"agent_harness-{version}-py3-none-any.whl").write_text("wheel", encoding="utf-8")
    (dist / f"agent_harness-{version}.tar.gz").write_text("sdist", encoding="utf-8")
    evidence = root / ".agent-harness" / "release" / "evidence"
    evidence.mkdir(parents=True)
    for name in (
        "package-build",
        "clean-install",
        "console-script",
        "demo-provider-audit",
        "demo-python-refactor",
        "template-validation",
    ):
        (evidence / f"{name}.json").write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    retrieval_scorecards = root / ".agent-harness" / "retrieval-scorecards"
    retrieval_scorecards.mkdir(parents=True)
    (retrieval_scorecards / "quality-demo.json").write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard.v1",
                "status": "passed",
                "index_id": "quality-demo",
            }
        ),
        encoding="utf-8",
    )
    demo = root / "examples" / "retrieval_quality"
    (demo / "docs" / "public").mkdir(parents=True)
    (demo / "docs" / "internal").mkdir(parents=True)
    (demo / "expected").mkdir()
    for relative in (
        "README.md",
        "config.v2.yaml",
        "policy.v2.yaml",
        "scorecard.yaml",
        "task.json",
        "expected/retrieval_index.json",
        "expected/retrieval_scorecard.json",
        "docs/public/architecture.md",
        "docs/public/coding-rules.md",
        "docs/public/public-notes.md",
        "docs/public/semantic-note.md",
        "docs/internal/denied-internal.md",
        "docs/internal/secret-internal.md",
    ):
        path = demo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "config.v2.yaml":
            path.write_text(
                "\n".join(
                    [
                        "schema_version: config.v2",
                        "project_name: retrieval-quality-demo",
                        "artifact_root: .agent-harness",
                        "default_policy: default",
                        "retrieval_backend: lexical",
                        "template_catalog: bundled",
                        "retrieval:",
                        "  dense:",
                        "    embedding_backend: fastembed",
                        "    remote_embeddings: false",
                        "  qdrant:",
                        "    backend: qdrant-local",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
        else:
            path.write_text("demo\n", encoding="utf-8")
    if include_skills:
        _write_skills_workflow_demo(root)
    if include_mcp:
        _write_mcp_boundary_demo(root)
        _write_mcp_ci_workflow(root)
    if include_orchestration:
        _write_orchestration_workflow_demo(root)
    if include_evidence_pack:
        _write_release_ready_evidence_pack(root, findings=evidence_findings or [])


def _write_release_ready_evidence_pack(root: Path, *, findings: list[dict[str, Any]]) -> None:
    evidence_root = root / ".agent-harness" / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    generated_at = "2026-05-01T00:00:00Z"
    pack_id = "release-ready-evidence-pack"
    pack = {
        "schema_version": "evidence_pack.v1",
        "pack_id": pack_id,
        "generated_at": generated_at,
        "profile": "default",
        "agent_harness_version": __version__,
        "workspace": {
            "project_name": "release-ready",
            "artifact_root": ".agent-harness",
            "config_path": "agent-harness.yaml",
            "default_policy": "default",
            "policy_path": "policies/default.json",
        },
        "domains": {
            "governance": {
                "status": "present",
                "message": "governance evidence packaged",
                "evidence_refs": [".agent-harness/evidence/evidence_manifest.v1.json"],
                "summary": {"checks": "passed"},
            },
            "release_readiness": {
                "status": "present",
                "message": "release evidence packaged",
                "evidence_refs": [".agent-harness/release/evidence/package-build.json"],
                "summary": {"status": "represented"},
            },
        },
        "governance_references": [".agent-harness/governance/governance_summary.v1.json"],
        "governance_hashes": {
            ".agent-harness/governance/governance_summary.v1.json": "hash-placeholder",
        },
        "release_readiness_reference": ".agent-harness/release/v9.9.9-readiness.json",
        "redaction_status": "metadata_only",
        "claim_status": "non_certifying",
        "disclaimer": (
            "This evidence pack supports review and audit preparation. It does not certify "
            "compliance with any legal, regulatory, security, or organizational framework."
        ),
    }
    manifest = {
        "schema_version": "evidence_manifest.v1",
        "pack_id": pack_id,
        "generated_at": generated_at,
        "files": [
            {"path": "evidence_pack.v1.json", "schema_version": "evidence_pack.v1"},
            {"path": "evidence_manifest.v1.json", "schema_version": "evidence_manifest.v1"},
            {"path": "evidence_index.v1.json", "schema_version": "evidence_index.v1"},
            {"path": "evidence_findings.v1.json", "schema_version": "evidence_findings.v1"},
            {"path": "control_mapping.v1.json", "schema_version": "control_mapping.v1"},
            {"path": "evidence_pack.v1.md", "schema_version": None},
            {"path": "control_mapping.v1.md", "schema_version": None},
        ],
    }
    index = {
        "schema_version": "evidence_index.v1",
        "pack_id": pack_id,
        "generated_at": generated_at,
        "entries": [
            {
                "artifact_type": "evidence_pack",
                "path": ".agent-harness/evidence/evidence_pack.v1.json",
                "content_hash": None,
                "schema_version": "evidence_pack.v1",
                "redaction_status": "metadata_only",
                "inclusion_status": "included",
            }
        ],
    }
    findings_export = {
        "schema_version": "evidence_findings.v1",
        "pack_id": pack_id,
        "generated_at": generated_at,
        "counts": {
            "total": len(findings),
            "by_severity": _finding_counts_by_severity(findings),
        },
        "findings": findings,
    }
    control_mapping = {
        "schema_version": "control_mapping.v1",
        "pack_id": pack_id,
        "generated_at": generated_at,
        "disclaimer": pack["disclaimer"],
        "limitations": ["Review-only release fixture."],
        "mappings": [
            {
                "theme_id": "release_readiness",
                "title": "Release Readiness",
                "coverage_status": "covered",
                "source_domains": ["release_readiness"],
                "evidence_refs": [".agent-harness/release/evidence/package-build.json"],
                "summary": "Release evidence is represented for review.",
                "limitations": ["No certification claim is made."],
            }
        ],
    }
    files = {
        "evidence_pack.v1.json": pack,
        "evidence_manifest.v1.json": manifest,
        "evidence_index.v1.json": index,
        "evidence_findings.v1.json": findings_export,
        "control_mapping.v1.json": control_mapping,
    }
    for filename, payload in files.items():
        (evidence_root / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_files = {
        "evidence_pack.v1.md": "# Evidence Pack\n",
        "control_mapping.v1.md": "# Control Mapping\n",
    }
    for filename, content in markdown_files.items():
        (evidence_root / filename).write_text(content, encoding="utf-8")
    _write_evidence_pack_checksums(evidence_root, sorted([*files, *markdown_files]))


def _finding_counts_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "info"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _write_evidence_pack_checksums(evidence_root: Path, filenames: list[str]) -> None:
    lines = []
    for filename in filenames:
        digest = hashlib.sha256((evidence_root / filename).read_bytes()).hexdigest()
        lines.append(f"{digest}  {filename}")
    (evidence_root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _passing_remote_ci(
    project_root: Path,
    target_commit: str,
    ci_run_id: str | None,
) -> dict[str, Any]:
    del project_root, target_commit, ci_run_id
    return {
        "run": {
            "source": "github_actions",
            "status": "completed",
            "conclusion": "success",
            "matches_target_commit": True,
        },
        "python_3_11": {"required": True, "status": "passed"},
        "python_3_12": {"required": True, "status": "passed"},
        "python_3_13": {"allowed_failure": True, "status": "failed_allowed"},
    }


def _write_skills_workflow_demo(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "examples" / "skills_workflow"
    target = root / "examples" / "skills_workflow"
    shutil.copytree(source, target, dirs_exist_ok=True)
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "skills-system.md").write_text(
        "\n".join(
            [
                "# Skill Pack System",
                "",
                "## Current Capabilities",
                "",
                "v1.5.0 local skills are bundled or explicitly configured local guidance.",
                "Runs with skills emit skill_manifest.v1 evidence.",
                "",
                "## Roadmap / Not Implemented Yet",
                "",
                "Remote skill catalogs, skill marketplace behavior, skill signing,",
                "hosted skill services, enterprise skill registries, organization-wide",
                "skill governance, centralized skill governance, and skill installation",
                "from network locations remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_mcp_boundary_demo(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "examples" / "mcp_boundary"
    target = root / "examples" / "mcp_boundary"
    shutil.copytree(source, target, dirs_exist_ok=True)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if "[project.optional-dependencies]" not in text:
        text += '\n[project.optional-dependencies]\nmcp = ["mcp>=1,<2"]\n'
    pyproject.write_text(text, encoding="utf-8")


def _write_mcp_ci_workflow(root: Path) -> None:
    workflow = root / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "\n".join(
            [
                "name: CI",
                "jobs:",
                "  release-evidence:",
                "    steps:",
                "      - name: Install dev, operator, and mcp dependencies",
                "        run: python -m pip install -e .[dev,operator,mcp]",
                "      - name: Release readiness report",
                "        run: python -m agent_harness release readiness",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_orchestration_workflow_demo(root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "examples" / "orchestration_workflow"
    target = root / "examples" / "orchestration_workflow"
    shutil.copytree(source, target, dirs_exist_ok=True)


def _write_inline_orchestration_workflow_demo(root: Path) -> None:
    demo = root / "examples" / "orchestration_workflow"
    (demo / "policies").mkdir(parents=True, exist_ok=True)
    (demo / "src").mkdir(parents=True, exist_ok=True)
    (demo / "README.md").write_text("v1.7.0 orchestration workflow demo\n", encoding="utf-8")
    (demo / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: orchestration-workflow-demo",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )
    policy = copy.deepcopy(DEFAULT_POLICY)
    policy["orchestration"] = {
        "enabled": True,
        "execution": "sequential",
        "allowed_roles": ["planner", "implementer", "reviewer", "tester"],
        "allow_nested": False,
    }
    policy["sensitivity_rules"] = [
        *policy["sensitivity_rules"],
        {"pattern": "src/calculator.py", "classification": "public"},
    ]
    (demo / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2),
        encoding="utf-8",
    )
    (demo / "src" / "calculator.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        encoding="utf-8",
    )
    (demo / "orchestration.json").write_text(
        json.dumps(_orchestration_workflow_spec(), indent=2),
        encoding="utf-8",
    )


def _orchestration_workflow_spec() -> dict[str, Any]:
    return {
        "schema_version": "orchestration.v1",
        "orchestration_id": "workflow-demo",
        "title": "v1.7.0 local orchestration workflow",
        "children": [
            {
                "child_id": "planner",
                "role": "planner",
                "title": "Plan the calculator review",
                "intent": "Inspect the calculator fixture and plan the follow-up checks.",
                "target_paths": ["src/calculator.py"],
                "allowed_tools": ["read_file", "search_code"],
            },
            {
                "child_id": "implementer",
                "role": "implementer",
                "title": "Assess implementation change",
                "intent": "Review the implementation path without mutating files.",
                "target_paths": ["src/calculator.py"],
                "allowed_tools": ["read_file", "search_code"],
                "depends_on": ["planner"],
            },
            {
                "child_id": "reviewer",
                "role": "reviewer",
                "title": "Review the candidate change",
                "intent": "Review the implementation assessment and source fixture.",
                "target_paths": ["src/calculator.py"],
                "allowed_tools": ["read_file", "search_code", "git_status"],
                "depends_on": ["implementer"],
            },
            {
                "child_id": "tester",
                "role": "tester",
                "title": "Plan deterministic tests",
                "intent": "Inspect the reviewer handoff and identify deterministic checks.",
                "target_paths": ["src/calculator.py"],
                "allowed_tools": ["read_file", "search_code", "run_tests"],
                "depends_on": ["reviewer"],
            },
        ],
    }


def _write_release_project_without_evidence(root: Path, version: str) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "agent-harness"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Agent Harness",
                "",
                "## What This Repo Proves",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## Roadmap / Not Enabled By Init",
                "",
                "Roadmap features remain future scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "prd-agent-harness-v1.0.0-mature-cli-runtime.md").write_text(
        "\n".join(
            [
                "# Agent Harness v1.0.0 / v1.0.0 PRD",
                "",
                "Agent Harness v1.0.0 is the v1.0.0 Mature CLI/runtime release.",
                "",
                "## Compatibility And Deprecation Policy",
                "",
                "v0.3.0 schemas are the v1.0.0 public baseline.",
                "",
                "## Implemented vs Roadmap",
                "",
                "Implemented capabilities are separate from roadmap scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-04-26\n\n- Release.\n",
        encoding="utf-8",
    )
