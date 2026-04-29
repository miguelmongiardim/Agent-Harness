from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

import pytest

import agent_harness.cli as cli
from agent_harness.cli import main
from tests.conftest import seed_project


def test_mcp_optional_extra_is_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    optional = pyproject["project"]["optional-dependencies"]

    assert optional["mcp"] == ["mcp>=1,<2"]


def test_mcp_help_states_v9_resources_prompts_only(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as raised:
        main(["mcp", "--help"])

    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert "resources/prompts only" in help_text
    assert "no tools" in help_text


def test_mcp_resources_list_exposes_run_resources_without_mcp_sdk(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    _, run_summary = _run_provider_audit_workspace(
        tmp_path,
        monkeypatch,
        capsys,
        run_id="run-mcp-list",
        fixed_time="2026-04-29T12:30:00Z",
    )

    assert main(["mcp", "resources", "list", "--json"]) == 0
    resource_list = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in resource_list["resources"]}

    assert resource_list["schema_version"] == "mcp_resource_list.v1"
    assert resource_list["profile"] == "default"
    assert "agent-harness://runs" in resource_uris
    assert f"agent-harness://runs/{run_summary['run_id']}/summary" in resource_uris
    assert f"agent-harness://runs/{run_summary['run_id']}/context" in resource_uris


def test_mcp_resources_read_returns_safe_run_summary_and_context_envelopes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    workspace, run_summary = _run_provider_audit_workspace(
        tmp_path,
        monkeypatch,
        capsys,
        run_id="run-mcp-read",
        fixed_time="2026-04-29T12:35:00Z",
    )
    run_id = run_summary["run_id"]

    assert (
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/summary", "--json"]) == 0
    )
    summary_envelope = json.loads(capsys.readouterr().out)

    assert summary_envelope["schema_version"] == "mcp_resource_envelope.v1"
    assert summary_envelope["uri"] == f"agent-harness://runs/{run_id}/summary"
    assert summary_envelope["mime_type"] == "application/json"
    assert summary_envelope["resource_type"] == "run_summary"
    assert summary_envelope["source_artifact"] == f".agent-harness/runs/{run_id}/summary.json"
    assert summary_envelope["source_schema_version"] == "summary.v1"
    assert summary_envelope["policy_profile"] == "default"
    assert summary_envelope["redaction_applied"] is False
    assert summary_envelope["denial_status"] == "allowed"
    assert summary_envelope["content"]["run_id"] == run_id
    assert str(workspace) not in json.dumps(summary_envelope)

    assert (
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/context", "--json"]) == 0
    )
    context_envelope = json.loads(capsys.readouterr().out)

    assert context_envelope["schema_version"] == "mcp_resource_envelope.v1"
    assert context_envelope["uri"] == f"agent-harness://runs/{run_id}/context"
    assert context_envelope["resource_type"] == "run_context"
    assert context_envelope["source_artifact"] == (
        f".agent-harness/runs/{run_id}/context_manifest.json"
    )
    assert context_envelope["source_schema_version"] == "context_manifest.v2"
    assert context_envelope["content"]["run_id"] == run_id
    assert str(workspace) not in json.dumps(context_envelope)


def test_mcp_allowed_resource_read_appends_metadata_only_access_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    workspace, run_summary = _run_provider_audit_workspace(
        tmp_path,
        monkeypatch,
        capsys,
        run_id="run-mcp-allowed-log",
        fixed_time="2026-04-29T13:05:00Z",
    )
    run_id = run_summary["run_id"]

    assert (
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/summary", "--json"]) == 0
    )
    envelope = json.loads(capsys.readouterr().out)
    log_path = workspace / ".agent-harness" / "mcp" / "access-log.jsonl"
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert envelope["content"]["run_id"] == run_id
    assert len(records) == 1
    assert records[0]["schema_version"] == "mcp_access_log.v1"
    assert records[0]["transport"] == "cli"
    assert records[0]["request_type"] == "resource_read"
    assert records[0]["resource_uri"] == f"agent-harness://runs/{run_id}/summary"
    assert records[0]["run_id"] == run_id
    assert records[0]["artifact_type"] == "run_summary"
    assert records[0]["policy_profile"] == "default"
    assert records[0]["result"] == "allowed"
    assert records[0]["redaction_applied"] is False
    assert records[0]["denial_reason"] is None
    assert "content" not in records[0]
    assert "Provider Audit Demo" not in json.dumps(records[0])


def test_mcp_resource_read_records_selected_profile(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    workspace, run_summary = _run_provider_audit_workspace(
        tmp_path,
        monkeypatch,
        capsys,
        run_id="run-mcp-profile",
        fixed_time="2026-04-29T13:20:00Z",
    )
    run_id = run_summary["run_id"]
    reviewer_policy = json.loads(
        (workspace / "policies" / "default.json").read_text(encoding="utf-8")
    )
    reviewer_policy["name"] = "reviewer"
    (workspace / "policies" / "reviewer.json").write_text(
        json.dumps(reviewer_policy, indent=2),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "mcp",
                "resources",
                "read",
                f"agent-harness://runs/{run_id}/summary",
                "--profile",
                "reviewer",
                "--json",
            ]
        )
        == 0
    )
    envelope = json.loads(capsys.readouterr().out)
    record = json.loads(
        (workspace / ".agent-harness" / "mcp" / "access-log.jsonl").read_text(encoding="utf-8")
    )

    assert envelope["policy_profile"] == "reviewer"
    assert record["policy_profile"] == "reviewer"
    assert record["result"] == "allowed"


def test_mcp_template_resources_read_through_template_registry(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["mcp", "resources", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in listed["resources"]}

    assert "agent-harness://templates" in resource_uris
    assert "agent-harness://templates/python-lib" in resource_uris

    assert main(["mcp", "resources", "read", "agent-harness://templates", "--json"]) == 0
    collection = json.loads(capsys.readouterr().out)

    assert collection["schema_version"] == "mcp_resource_envelope.v1"
    assert collection["resource_type"] == "template_collection"
    assert collection["source_schema_version"] == "template_registry_record.v1"
    assert collection["denial_status"] == "allowed"
    assert collection["content"]["schema_version"] == "mcp_template_collection.v1"
    assert "python-lib" in {
        template["template_id"] for template in collection["content"]["templates"]
    }
    assert str(tmp_path) not in json.dumps(collection)

    assert main(["mcp", "resources", "read", "agent-harness://templates/python-lib", "--json"]) == 0
    detail = json.loads(capsys.readouterr().out)

    assert detail["resource_type"] == "template_detail"
    assert detail["source_artifact"] == "bundled_templates/python-lib/template.v2.toml"
    assert detail["source_schema_version"] == "template.v2"
    assert detail["content"]["schema_version"] == "template_detail.v1"
    assert detail["content"]["template_id"] == "python-lib"
    assert "README.md" in {file["path"] for file in detail["content"]["files"]}
    assert str(tmp_path) not in json.dumps(detail)


def test_mcp_skill_resources_read_through_skill_registry(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["mcp", "resources", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in listed["resources"]}

    assert "agent-harness://skills" in resource_uris
    assert "agent-harness://skills/tdd" in resource_uris

    assert main(["mcp", "resources", "read", "agent-harness://skills", "--json"]) == 0
    collection = json.loads(capsys.readouterr().out)

    assert collection["resource_type"] == "skill_collection"
    assert collection["source_schema_version"] == "skill_registry_record.v1"
    assert collection["content"]["schema_version"] == "mcp_skill_collection.v1"
    assert "tdd" in {skill["skill_id"] for skill in collection["content"]["skills"]}
    assert str(tmp_path) not in json.dumps(collection)

    assert main(["mcp", "resources", "read", "agent-harness://skills/tdd", "--json"]) == 0
    detail = json.loads(capsys.readouterr().out)

    assert detail["resource_type"] == "skill_detail"
    assert detail["source_artifact"] == "bundled_skills/tdd/SKILL.md"
    assert detail["source_schema_version"] == "skill_detail.v1"
    assert detail["content"]["schema_version"] == "skill_detail.v1"
    assert detail["content"]["skill_id"] == "tdd"
    assert detail["content"]["name"] == "Test-Driven Development"
    assert detail["content"]["validation_status"] == "passed"
    assert detail["content"]["body_summary"].startswith("# Test-Driven Development")
    assert str(tmp_path) not in json.dumps(detail)


def test_mcp_policy_resource_reads_summary_through_policy_service(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert main(["mcp", "resources", "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    resource_uris = {resource["uri"] for resource in listed["resources"]}

    assert "agent-harness://policies/default" in resource_uris

    assert main(["mcp", "resources", "read", "agent-harness://policies/default", "--json"]) == 0
    envelope = json.loads(capsys.readouterr().out)

    assert envelope["resource_type"] == "policy_summary"
    assert envelope["source_artifact"] == "policies/default.json"
    assert envelope["source_schema_version"] == "policy.v2"
    assert envelope["policy_profile"] == "default"
    assert envelope["content"]["schema_version"] == "mcp_policy_summary.v1"
    assert envelope["content"]["name"] == "default"
    assert "read_file" in envelope["content"]["allowed_tools"]
    assert envelope["content"]["template_capabilities"]["default_action"] == "deny"
    assert str(tmp_path) not in json.dumps(envelope)


def test_mcp_serve_reports_missing_optional_sdk(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_mcp_sdk_available", lambda: False, raising=False)

    assert main(["mcp", "serve"]) == 1
    captured = capsys.readouterr()

    assert "MCP SDK" in captured.err
    assert "agent-harness[mcp]" in captured.err
    assert captured.out == ""


def _run_provider_audit_workspace(
    tmp_path: Path,
    monkeypatch,
    capsys,
    *,
    run_id: str,
    fixed_time: str,
) -> tuple[Path, dict[str, object]]:  # type: ignore[no-untyped-def]
    workspace = _copy_provider_audit_workspace(tmp_path)
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", run_id)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", fixed_time)
    monkeypatch.setenv(
        "AGENT_HARNESS_PROVIDER_AUDIT_ENDPOINT",
        "recorded://openai_compatible/read_only",
    )
    monkeypatch.setenv("AGENT_HARNESS_PROVIDER_AUDIT_API_KEY", "provider-audit-test-secret")

    assert main(["run", "task.json", "--auto-approve"]) == 0
    run_summary = json.loads(capsys.readouterr().out)
    return workspace, run_summary


def _copy_provider_audit_workspace(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "examples" / "provider_audit"
    destination = tmp_path / "provider_audit"
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".agent-harness"))
    return destination
