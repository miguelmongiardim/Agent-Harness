from __future__ import annotations

import json
import shutil
import tomllib
from pathlib import Path

import pytest

import agent_harness.cli as cli
from agent_harness.cli import main


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
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/summary", "--json"])
        == 0
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
        main(["mcp", "resources", "read", f"agent-harness://runs/{run_id}/context", "--json"])
        == 0
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
