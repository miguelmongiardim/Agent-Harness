from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent_harness.cli as cli
from agent_harness import __version__
from agent_harness.cli import main
from tests.conftest import seed_project


def _simulate_missing_operator_dependencies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli, "_operator_dependencies_available", lambda: False)


def test_operator_optional_extra_and_test_client_dependency_are_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    optional = pyproject["project"]["optional-dependencies"]

    assert "fastapi>=0.110" in optional["operator"]
    assert "uvicorn[standard]>=0.27" in optional["operator"]
    assert "httpx>=0.27" in optional["dev"]


def test_serve_is_present_in_cli_help(capsys) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit) as raised:
        main(["--help"])

    assert raised.value.code == 0
    assert "serve" in capsys.readouterr().out


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.25", "8.8.8.8", "example.com"])
def test_serve_rejects_non_loopback_host_before_startup(
    tmp_path: Path,
    monkeypatch,
    capsys,
    host: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)

    assert main(["serve", "--host", host]) == 1
    captured = capsys.readouterr()

    assert "loopback" in captured.err
    assert host in captured.err
    assert not (tmp_path / ".agent-harness" / "runs").exists()


def test_serve_valid_loopback_reports_operator_extra_install_hint(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _simulate_missing_operator_dependencies(monkeypatch)
    seed_project(tmp_path)

    assert main(["serve", "--host", "127.0.0.1"]) == 1
    captured = capsys.readouterr()

    assert "agent-harness[operator]" in captured.err
    assert "FastAPI" in captured.err
    assert "uvicorn" in captured.err


def test_serve_with_operator_extra_starts_loopback_app(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    calls = []

    import uvicorn

    def fake_run(app, *, host: str, port: int) -> None:  # type: ignore[no-untyped-def]
        calls.append({"app": app, "host": host, "port": port})

    monkeypatch.setattr(uvicorn, "run", fake_run)

    assert (
        main(
            [
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "9876",
                "--token",
                "provided-secret",
                "--profile",
                "default",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()

    assert len(calls) == 1
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 9876
    assert TestClient(calls[0]["app"]).get("/health").json()["agent_harness_version"] == __version__
    assert "provided-secret" not in captured.out
    assert "provided-secret" not in captured.err


def test_serve_defaults_print_generated_token_once_without_persisting(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _simulate_missing_operator_dependencies(monkeypatch)
    seed_project(tmp_path)

    assert main(["serve"]) == 1
    captured = capsys.readouterr()
    token_lines = [
        line for line in captured.out.splitlines() if line.startswith("Operator token: ")
    ]

    assert "127.0.0.1" in captured.out
    assert "8765" in captured.out
    assert "default" in captured.out
    assert len(token_lines) == 1
    token = token_lines[0].removeprefix("Operator token: ")
    assert len(token) >= 32
    assert token not in captured.err
    assert not (tmp_path / ".agent-harness").exists()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_serve_accepts_allowed_loopback_hosts_without_echoing_supplied_token(
    tmp_path: Path,
    monkeypatch,
    capsys,
    host: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _simulate_missing_operator_dependencies(monkeypatch)
    seed_project(tmp_path)

    assert main(["serve", "--host", host, "--token", "provided-secret"]) == 1
    captured = capsys.readouterr()

    assert host in captured.out
    assert "agent-harness[operator]" in captured.err
    assert "loopback" not in captured.err
    assert "provided-secret" not in captured.out
    assert "provided-secret" not in captured.err
