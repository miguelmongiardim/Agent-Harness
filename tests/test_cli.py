from __future__ import annotations

from pathlib import Path

from agent_harness.cli import main


def test_cli_init_and_template_apply(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    assert (tmp_path / "agent-harness.yaml").exists()
    assert (tmp_path / "policies" / "default.json").exists()

    destination = tmp_path / "scratch"
    assert main(["template", "apply", "python-lib", "--destination", str(destination)]) == 0
    assert (destination / "pyproject.toml").exists()
    assert (destination / "src" / "example_python_lib" / "core.py").exists()
