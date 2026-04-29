from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from tests.conftest import seed_project


def test_mcp_file_uri_read_returns_denial_envelope_and_access_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-29T13:00:00Z")
    secret_path = tmp_path / "secrets.env"
    secret_path.write_text("API_KEY=do-not-leak\n", encoding="utf-8")

    assert main(["mcp", "resources", "read", secret_path.as_uri(), "--json"]) == 1
    envelope = json.loads(capsys.readouterr().out)

    assert envelope["schema_version"] == "mcp_resource_envelope.v1"
    assert envelope["uri"] == secret_path.as_uri()
    assert envelope["resource_type"] == "denial"
    assert envelope["policy_profile"] == "default"
    assert envelope["denial_status"] == "denied"
    assert envelope["metadata"]["denial_reason"] == "unsupported_uri_scheme"
    assert envelope["content"] is None
    assert str(tmp_path) not in json.dumps(envelope)
    assert "do-not-leak" not in json.dumps(envelope)

    log_path = tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl"
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

    assert len(records) == 1
    assert records[0]["schema_version"] == "mcp_access_log.v1"
    assert records[0]["transport"] == "cli"
    assert records[0]["request_type"] == "resource_read"
    assert records[0]["resource_uri"] == secret_path.as_uri()
    assert records[0]["policy_profile"] == "default"
    assert records[0]["result"] == "denied"
    assert records[0]["denial_reason"] == "unsupported_uri_scheme"
    assert "content" not in records[0]
    assert "do-not-leak" not in json.dumps(records[0])


@pytest.mark.parametrize(
    ("uri", "reason"),
    [
        ("agent-harness://runs/../summary", "unsafe_run_id"),
        ("C:/Users/example/secrets.env", "unsupported_uri_scheme"),
        ("agent-harness://runs/run-safe/summary?raw=true", "query_or_fragment_not_allowed"),
        ("agent-harness://runs/run-safe/summary#raw", "query_or_fragment_not_allowed"),
        ("agent-harness://workspace/secrets.env", "unknown_resource"),
        ("agent-harness://runs/run-safe/provider-raw", "unknown_resource"),
        ("agent-harness://runs/run$bad/summary", "unsafe_run_id"),
    ],
)
def test_mcp_unsafe_resource_uri_returns_denial_envelope_and_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
    uri: str,
    reason: str,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-29T13:10:00Z")

    assert main(["mcp", "resources", "read", uri, "--json"]) == 1
    envelope = json.loads(capsys.readouterr().out)
    record = json.loads(
        (tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl").read_text(
            encoding="utf-8"
        )
    )

    assert envelope["denial_status"] == "denied"
    assert envelope["metadata"]["denial_reason"] == reason
    assert envelope["content"] is None
    assert str(tmp_path) not in json.dumps(envelope)
    assert record["result"] == "denied"
    assert record["denial_reason"] == reason
    assert record["resource_uri"] == uri
    assert "content" not in record


def test_mcp_unknown_profile_returns_denial_envelope_and_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-29T13:15:00Z")

    uri = "agent-harness://runs/run-safe/summary"
    assert main(["mcp", "resources", "read", uri, "--profile", "missing", "--json"]) == 1
    envelope = json.loads(capsys.readouterr().out)
    record = json.loads(
        (tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl").read_text(
            encoding="utf-8"
        )
    )

    assert envelope["denial_status"] == "denied"
    assert envelope["policy_profile"] == "missing"
    assert envelope["metadata"]["denial_reason"] == "unknown_profile"
    assert "policy profile not found" not in json.dumps(envelope)
    assert str(tmp_path) not in json.dumps(envelope)
    assert record["policy_profile"] == "missing"
    assert record["result"] == "denied"
    assert record["denial_reason"] == "unknown_profile"
