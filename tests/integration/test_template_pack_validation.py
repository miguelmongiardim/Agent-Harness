from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_harness.cli import main


def test_template_pack_validate_rejects_unsafe_local_pack(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "unsafe-pack"
    _write_pack(
        pack,
        manifest_extra="""
[[files]]
path = "../escape.txt"
source = "files/escape.txt"

[[files]]
path = "/absolute.txt"
source = "files/absolute.txt"

[[files]]
path = "src/token.py"
source = "https://example.invalid/token.py"

[[files]]
path = "src/undeclared.py"
source = "files/undeclared.py"

[[files]]
path = "src/credential.py"
source = "files/credential.py"
""",
        files={
            "files/escape.txt": "outside\n",
            "files/absolute.txt": "absolute\n",
            "files/undeclared.py": 'PACKAGE = "{{ package_name }}"\n',
            "files/credential.py": 'API_KEY = "sk-live-secret"\n',
        },
    )

    assert main(["template", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "template_pack_validation.v1"
    assert report["status"] == "failed"
    assert report["pack_path"] == str(pack.resolve())
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {
        "path_traversal",
        "absolute_path",
        "remote_source",
        "undeclared_placeholder",
        "secret_like_value",
    } <= rule_ids
    assert all(diagnostic["severity"] == "error" for diagnostic in report["diagnostics"])


def test_template_pack_validate_accepts_valid_local_pack(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "valid-pack"
    _write_pack(
        pack,
        parameters="""
[parameters.package_name]
type = "path_fragment"
default = "example_pkg"
required = false
""",
        manifest_extra="""
[[files]]
path = "src/{{ package_name }}/__init__.py"
source = "files/src/example_pkg/__init__.py.template"
""",
        files={
            "files/src/example_pkg/__init__.py.template": 'PACKAGE = "{{ package_name }}"\n',
        },
    )

    assert main(["template", "pack", "validate", str(pack)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["diagnostics"] == []


def test_template_validate_python_lib_uses_pack_validator(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["template", "validate", "python-lib"]) == 0
    report = json.loads(capsys.readouterr().out)
    result = report["templates"][0]

    assert result["template_id"] == "python-lib"
    assert result["status"] == "passed"
    assert result["diagnostics"] == []


def test_template_pack_validate_reports_manifest_and_placeholder_errors(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "manifest-errors"
    _write_pack(
        pack,
        template_id="Bad_ID",
        version="1",
        minimum_agent_harness_version=">=1.4",
        maximum_agent_harness_version="^2",
        manifest_extra="""
[hooks]
post_apply = "run-me"

[scripts]
install = "setup.ps1"

[[files]]
path = "src/app.py"
source = "files/app.py"
""",
        files={"files/app.py": 'VALUE = "{{ package-name | lower }}"\n'},
    )

    assert main(["template", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {
        "invalid_template_id",
        "invalid_template_version",
        "invalid_compatibility_version",
        "hook_declaration",
        "script_declaration",
        "unsupported_placeholder",
    } <= rule_ids


def test_template_pack_validate_reports_source_and_generated_file_errors(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "source-errors"
    _write_pack(
        pack,
        manifest_extra="""
[[files]]
path = ".hidden"
source = "files/hidden.txt"

[[files]]
path = "missing.txt"
source = "files/missing.txt"

[[files]]
path = "binary.txt"
source = "files/binary.txt"
""",
        files={
            "files/hidden.txt": "hidden\n",
            "files/unlisted.txt": "unlisted\n",
        },
    )
    (pack / "files" / "binary.txt").write_bytes(b"\xff\xfe\x00\x00")

    assert main(["template", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {
        "hidden_generated_file",
        "missing_source_file",
        "non_utf8_source",
        "unlisted_generated_file",
    } <= rule_ids


def test_template_pack_validate_reports_symlink_escape(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    pack = tmp_path / "symlink-pack"
    _write_pack(
        pack,
        manifest_extra="""
[[files]]
path = "safe.txt"
source = "files/link.txt"
""",
        files={},
    )
    link = pack / "files" / "link.txt"
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link)
    except OSError as exc:
        pytest.skip(f"symlink creation is not available in this environment: {exc}")

    assert main(["template", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert "symlink_escape" in rule_ids


def test_template_pack_validate_reports_generated_marker_and_example_errors(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "example-errors"
    _write_pack(
        pack,
        manifest_extra="""
[[files]]
path = "examples/task.json"
source = "files/task.json"

[[files]]
path = "docs/citation.md"
source = "files/citation.md"

[[files]]
path = "docs/private.md"
source = "files/private.md"
""",
        files={
            "files/task.json": json.dumps({"schema_version": "task.v2"}),
            "files/citation.md": "[citation needed]\n",
            "files/private.md": "See /mnt/data/private.txt\n",
        },
    )

    assert main(["template", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {
        "generated_example_invalid",
        "generated_citation_marker",
        "private_uploaded_file_reference",
    } <= rule_ids


def _write_pack(
    pack: Path,
    *,
    manifest_extra: str,
    files: dict[str, str],
    parameters: str = "",
    template_id: str = "unsafe-pack",
    version: str = "1.0.0",
    minimum_agent_harness_version: str = "0.2.0",
    maximum_agent_harness_version: str | None = None,
) -> None:
    pack.mkdir(parents=True)
    maximum = (
        f'maximum_agent_harness_version = "{maximum_agent_harness_version}"\n'
        if maximum_agent_harness_version is not None
        else ""
    )
    (pack / "template.v2.toml").write_text(
        f"""
schema_version = "template.v2"
template_id = "{template_id}"
version = "{version}"
title = "Unsafe Pack"
description = "Fixture pack with unsafe declarations."
minimum_agent_harness_version = "{minimum_agent_harness_version}"
{maximum}
required_capabilities = ["python.library"]
{parameters}

[generated_schema_versions]
config = "config.v2"
policy = "policy.v2"
task = "task.v2"
template = "template.v2"

[provider_requirements]
required = false
profiles = []

[policy_requirements]
required_template_capabilities = ["python.library"]
required_tools = ["patch_file"]

[retrieval_assumptions]
backend = "lexical"
remote_embeddings = false

[eval_or_demo_metadata]
kind = "demo"
commands = ["python -m pytest"]
{manifest_extra}
""".lstrip(),
        encoding="utf-8",
    )
    for relative, content in files.items():
        path = pack / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
