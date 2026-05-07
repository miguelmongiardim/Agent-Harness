from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_template_list_and_show_include_configured_local_pack(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_local_pack(
        tmp_path / "local-templates" / "acme-lib",
        template_id="acme-lib",
        title="Acme Library",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["template", "list"]) == 0
    rows = {
        parts[0]: parts
        for line in capsys.readouterr().out.splitlines()
        if (parts := line.split("\t"))
    }

    assert rows["acme-lib"] == [
        "acme-lib",
        "1.0.0",
        "Acme Library",
        "local_pack",
        "compatible",
    ]

    assert main(["template", "show", "acme-lib"]) == 0
    detail = json.loads(capsys.readouterr().out)

    assert detail["template_id"] == "acme-lib"
    assert detail["source_type"] == "local_pack"
    assert detail["bundle_path"] == "local-templates/acme-lib/template.v2.toml"
    assert detail["parameters"]["package_name"]["type"] == "path_fragment"
    assert detail["files"] == [
        {
            "path": "src/{{ package_name }}/__init__.py",
            "content": 'PACKAGE = "{{ package_name }}"\n',
        }
    ]


def test_local_pack_apply_renders_typed_parameters_in_paths_and_content(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_rendering_pack(tmp_path / "local-templates" / "typed-pack")
    monkeypatch.chdir(tmp_path)

    assert (
        main(
            [
                "template",
                "apply",
                "typed-pack",
                "--target",
                str(tmp_path / "scaffold"),
                "--param",
                "package_name=custom_pkg",
                "--param",
                "license=apache",
                "--param",
                "feature_enabled=false",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)

    assert summary["status"] == "completed"
    generated = tmp_path / "scaffold" / "src" / "custom_pkg" / "apache-false.txt"
    assert generated.read_text(encoding="utf-8") == (
        "package=custom_pkg\nlicense=apache\nenabled=false\n"
    )


def test_invalid_local_pack_reports_diagnostics_and_is_not_usable(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_invalid_local_pack(tmp_path / "local-templates" / "invalid-pack")
    monkeypatch.chdir(tmp_path)

    assert main(["template", "validate", "--all"]) == 1
    report = json.loads(capsys.readouterr().out)
    invalid = next(entry for entry in report["templates"] if entry["template_id"] == "invalid-pack")

    assert invalid["status"] == "failed"
    assert invalid["source_type"] == "local_pack"
    assert invalid["message"] == "template pack validation failed"
    assert [diagnostic["rule_id"] for diagnostic in invalid["diagnostics"]] == [
        "hidden_generated_file"
    ]

    assert main(["template", "show", "invalid-pack"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "template pack validation failed" in captured.err


def test_valid_local_pack_template_validation_runs_in_sandbox(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_local_pack(
        tmp_path / "local-templates" / "acme-lib",
        template_id="acme-lib",
        title="Acme Library",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["template", "validate", "acme-lib"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "passed"
    assert report["templates"][0]["source_type"] == "local_pack"
    assert report["templates"][0]["apply"]["status"] == "completed"


def test_local_pack_apply_rejects_invalid_parameters_before_writing(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_rendering_pack(tmp_path / "local-templates" / "typed-pack")
    monkeypatch.chdir(tmp_path)

    cases = [
        ([], "missing required template parameter: package_name"),
        (
            ["--param", "package_name=custom_pkg", "--param", "license=gpl"],
            "invalid choice for template parameter license",
        ),
        (
            ["--param", "package_name=custom_pkg", "--param", "feature_enabled=yes"],
            "boolean template parameter must be true or false: feature_enabled",
        ),
        (
            ["--param", "package_name=../escape"],
            "invalid path_fragment template parameter: package_name",
        ),
        (
            ["--param", "package_name=C:\\escape"],
            "path_fragment template parameter cannot be absolute: package_name",
        ),
    ]

    for index, (params, message) in enumerate(cases):
        target = tmp_path / f"scaffold-{index}"
        assert main(["template", "apply", "typed-pack", "--target", str(target), *params]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert message in captured.err
        assert not target.exists()


def test_local_pack_duplicate_id_with_bundled_template_fails_clearly(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: local-pack-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                "    - local-templates",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_local_pack(
        tmp_path / "local-templates" / "python-lib-copy",
        template_id="python-lib",
        title="Duplicate Python Library",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["template", "list"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "duplicate template ids discovered: python-lib" in captured.err


def _write_local_pack(pack: Path, *, template_id: str, title: str) -> None:
    pack.mkdir(parents=True)
    (pack / "template.v2.toml").write_text(
        f"""
schema_version = "template.v2"
template_id = "{template_id}"
version = "1.0.0"
title = "{title}"
description = "Local template pack fixture."
minimum_agent_harness_version = "0.2.0"
required_capabilities = ["python.library"]

[parameters.package_name]
type = "path_fragment"
default = "acme_lib"
required = false

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

[[files]]
path = "src/{{{{ package_name }}}}/__init__.py"
source = "files/src/acme_lib/__init__.py.template"
""".lstrip(),
        encoding="utf-8",
    )
    source = pack / "files" / "src" / "acme_lib" / "__init__.py.template"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('PACKAGE = "{{ package_name }}"\n', encoding="utf-8")


def _write_rendering_pack(pack: Path) -> None:
    pack.mkdir(parents=True)
    (pack / "template.v2.toml").write_text(
        """
schema_version = "template.v2"
template_id = "typed-pack"
version = "1.0.0"
title = "Typed Parameter Pack"
description = "Local template pack with typed render parameters."
minimum_agent_harness_version = "0.2.0"
required_capabilities = ["python.library"]

[parameters.package_name]
type = "path_fragment"
required = true

[parameters.license]
type = "choice"
choices = ["mit", "apache"]
default = "mit"
required = false

[parameters.feature_enabled]
type = "boolean"
default = true
required = false

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

[[files]]
path = "src/{{ package_name }}/{{ license }}-{{ feature_enabled }}.txt"
source = "files/template.txt"
""".lstrip(),
        encoding="utf-8",
    )
    source = pack / "files" / "template.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "package={{ package_name }}\nlicense={{ license }}\nenabled={{ feature_enabled }}\n",
        encoding="utf-8",
    )


def _write_invalid_local_pack(pack: Path) -> None:
    pack.mkdir(parents=True)
    (pack / "template.v2.toml").write_text(
        """
schema_version = "template.v2"
template_id = "invalid-pack"
version = "1.0.0"
title = "Invalid Pack"
description = "Local template pack fixture with a denied target."
minimum_agent_harness_version = "0.2.0"
required_capabilities = ["python.library"]

[parameters.package_name]
type = "path_fragment"
default = "invalid_pack"
required = false

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

[[files]]
path = ".secret.txt"
source = "files/secret.txt"
""".lstrip(),
        encoding="utf-8",
    )
    source = pack / "files" / "secret.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("secret\n", encoding="utf-8")
