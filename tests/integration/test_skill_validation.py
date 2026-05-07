from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agent_harness.cli import main


def test_skill_list_rejects_local_skill_that_shadows_bundled(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    _write_skill(
        tmp_path / "skills" / "write-a-prd" / "SKILL.md",
        skill_id="write-a-prd",
        name="Shadow Write a PRD",
        description="This local skill must not silently shadow the bundled skill.",
    )

    assert main(["skill", "list"]) == 1
    captured = capsys.readouterr()

    assert "duplicate skill ids discovered: write-a-prd" in captured.err


def test_skill_list_discovers_only_configured_local_dirs(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["configured-skills"])
    _write_skill(
        tmp_path / "configured-skills" / "local-planning" / "SKILL.md",
        skill_id="local-planning",
        name="Local Planning",
        description="A configured local planning skill.",
    )
    _write_skill(
        tmp_path / "unconfigured-skills" / "hidden-skill" / "SKILL.md",
        skill_id="hidden-skill",
        name="Hidden Skill",
        description="An unconfigured local skill.",
    )

    assert main(["skill", "list"]) == 0
    rows = [line.split("\t") for line in capsys.readouterr().out.strip().splitlines()]
    by_id = {row[0]: row for row in rows}

    assert "local-planning" in by_id
    assert by_id["local-planning"][3] == "local"
    assert by_id["local-planning"][5] == "passed"
    assert "hidden-skill" not in by_id


def test_skill_list_accepts_config_without_skills_block(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_without_skills(tmp_path)
    _write_skill(
        tmp_path / "skills" / "hidden-skill" / "SKILL.md",
        skill_id="hidden-skill",
        name="Hidden Skill",
        description="An unconfigured local skill.",
    )

    assert main(["skill", "list"]) == 0
    rows = [line.split("\t") for line in capsys.readouterr().out.strip().splitlines()]
    by_id = {row[0]: row for row in rows}
    assert "write-a-prd" in by_id
    assert "hidden-skill" not in by_id


def test_skill_show_and_render_support_valid_local_skill(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    _write_skill(
        tmp_path / "skills" / "local-planning" / "SKILL.md",
        skill_id="local-planning",
        name="Local Planning",
        description="A configured local planning skill.",
        body="This local skill can be rendered after validation.",
    )

    assert main(["skill", "show", "local-planning"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["source_type"] == "local"
    assert detail["source"] == "skills/local-planning/SKILL.md"
    assert detail["validation_status"] == "passed"
    assert re.fullmatch(r"[a-f0-9]{64}", detail["skill_hash"])

    assert main(["skill", "render", "local-planning"]) == 0
    rendered = capsys.readouterr().out
    assert "source_type: local" in rendered
    assert "source: skills/local-planning/SKILL.md" in rendered
    assert "This local skill can be rendered after validation." in rendered

    assert main(["skill", "validate", "local-planning"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["source_type"] == "local"
    assert report["source"] == "skills/local-planning/SKILL.md"
    assert report["status"] == "passed"


def test_skill_list_expands_user_local_skill_dirs(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.chdir(project)
    _write_config_with_skill_dirs(project, ["~/skills"])
    _write_skill(
        home / "skills" / "user-local" / "SKILL.md",
        skill_id="user-local",
        name="User Local",
        description="A configured user-local skill.",
    )

    assert main(["skill", "list"]) == 0
    rows = [line.split("\t") for line in capsys.readouterr().out.strip().splitlines()]
    by_id = {row[0]: row for row in rows}
    assert by_id["user-local"][3] == "local"
    assert by_id["user-local"][5] == "passed"

    assert main(["skill", "show", "user-local"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert Path(detail["source"]) == (home / "skills" / "user-local" / "SKILL.md").resolve()


def test_skill_list_reports_missing_configured_local_dir(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["missing-skills"])

    assert main(["skill", "list"]) == 0
    captured = capsys.readouterr()

    assert "write-a-prd" in captured.out
    assert "missing skill directory: missing-skills" in captured.err


def test_invalid_local_skill_is_visible_with_diagnostics_but_not_rendered(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    invalid = tmp_path / "skills" / "invalid-local" / "SKILL.md"
    invalid.parent.mkdir(parents=True)
    invalid.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: invalid-local",
                "name: Invalid Local",
                "version: 1.0.0",
                'description: ""',
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "list"]) == 0
    rows = [line.split("\t") for line in capsys.readouterr().out.strip().splitlines()]
    by_id = {row[0]: row for row in rows}
    assert by_id["invalid-local"][3] == "local"
    assert by_id["invalid-local"][5] == "failed"

    assert main(["skill", "show", "invalid-local"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["validation_status"] == "failed"
    assert detail["source_type"] == "local"
    rule_ids = {diagnostic["rule_id"] for diagnostic in detail["diagnostics"]}
    assert {"empty_skill_description", "missing_body"} <= rule_ids

    assert main(["skill", "render", "invalid-local"]) == 1
    assert "skill validation failed: invalid-local" in capsys.readouterr().err

    assert main(["skill", "validate", "invalid-local"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "failed"
    assert report["source_type"] == "local"


def test_non_utf8_local_skill_is_visible_with_diagnostics(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    invalid = tmp_path / "skills" / "binary-local" / "SKILL.md"
    invalid.parent.mkdir(parents=True)
    invalid.write_bytes(b"\xff\xfe\x00\x00")

    assert main(["skill", "list"]) == 0
    rows = [line.split("\t") for line in capsys.readouterr().out.strip().splitlines()]
    by_id = {row[0]: row for row in rows}
    assert by_id["binary-local"][3] == "local"
    assert by_id["binary-local"][5] == "failed"

    assert main(["skill", "show", "binary-local"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["validation_status"] == "failed"
    assert detail["source_type"] == "local"
    assert detail["source"] == "skills/binary-local/SKILL.md"
    assert {diagnostic["rule_id"] for diagnostic in detail["diagnostics"]} == {"non_utf8_skill"}

    assert main(["skill", "render", "binary-local"]) == 1
    assert "skill validation failed: binary-local" in capsys.readouterr().err


def test_skill_list_rejects_duplicate_local_skill_ids(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills-a", "skills-b"])
    _write_skill(
        tmp_path / "skills-a" / "duplicate-skill" / "SKILL.md",
        skill_id="duplicate-skill",
        name="Duplicate Skill A",
        description="The first duplicate skill.",
    )
    _write_skill(
        tmp_path / "skills-b" / "duplicate-skill" / "SKILL.md",
        skill_id="duplicate-skill",
        name="Duplicate Skill B",
        description="The second duplicate skill.",
    )

    assert main(["skill", "list"]) == 1
    assert "duplicate skill ids discovered: duplicate-skill" in capsys.readouterr().err


def test_skill_list_reports_required_bundled_skills(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["skill", "list"]) == 0
    output = capsys.readouterr().out.strip().splitlines()

    rows = [line.split("\t") for line in output]
    by_id = {row[0]: row for row in rows}

    assert {
        "write-a-prd",
        "prd-to-plan",
        "tdd",
        "prd-plan-tdd-workflow",
    } <= set(by_id)
    for skill_id in {
        "write-a-prd",
        "prd-to-plan",
        "tdd",
        "prd-plan-tdd-workflow",
    }:
        row = by_id[skill_id]
        assert len(row) == 7
        assert row[1] == "1.0.0"
        assert row[2]
        assert row[3] == "bundled"
        assert row[4] == "compatible"
        assert row[5] == "passed"
        assert row[6]


def test_skill_show_reports_metadata_hash_and_body_summary(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["skill", "show", "prd-plan-tdd-workflow"]) == 0
    detail = json.loads(capsys.readouterr().out)

    assert detail["schema_version"] == "skill_detail.v1"
    assert detail["skill_id"] == "prd-plan-tdd-workflow"
    assert detail["version"] == "1.0.0"
    assert detail["name"] == "PRD Plan TDD Workflow"
    assert detail["source_type"] == "bundled"
    assert detail["source"] == "bundled_skills/prd-plan-tdd-workflow/SKILL.md"
    assert detail["compatibility_status"] == "compatible"
    assert detail["validation_status"] == "passed"
    assert detail["diagnostics"] == []
    assert re.fullmatch(r"[a-f0-9]{64}", detail["skill_hash"])
    assert "non-trivial system" in detail["body_summary"]
    assert detail["related_skills"] == ["write-a-prd", "prd-to-plan", "tdd"]


def test_skill_render_outputs_metadata_header_and_markdown_body(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["skill", "render", "prd-plan-tdd-workflow"]) == 0
    rendered = capsys.readouterr().out

    assert rendered.startswith("# Skill: PRD Plan TDD Workflow")
    assert "skill_id: prd-plan-tdd-workflow" in rendered
    assert "version: 1.0.0" in rendered
    assert "source: bundled_skills/prd-plan-tdd-workflow/SKILL.md" in rendered
    assert "skill_hash: " in rendered
    assert "# PRD -> Plan -> TDD Workflow" in rendered
    assert "vertical tracer-bullet phases" in rendered


def test_skill_pack_validate_reports_all_skills_without_mutation(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    pack = tmp_path / "skill-pack"
    valid = pack / "valid" / "SKILL.md"
    invalid = pack / "invalid" / "SKILL.md"
    valid.parent.mkdir(parents=True)
    invalid.parent.mkdir(parents=True)
    valid.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: valid-local-skill",
                "name: Valid Local Skill",
                "version: 1.0.0",
                "description: A valid local skill.",
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
                "# Valid Local Skill",
                "",
                "This skill is safe to validate.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    invalid.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: invalid-local-skill",
                "name: Invalid Local Skill",
                "version: 1.0.0",
                'description: ""',
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )
    before = sorted(path.relative_to(pack).as_posix() for path in pack.rglob("*"))

    assert main(["skill", "pack", "validate", str(pack)]) == 1
    report = json.loads(capsys.readouterr().out)
    after = sorted(path.relative_to(pack).as_posix() for path in pack.rglob("*"))

    assert before == after
    assert not (pack / ".agent-harness").exists()
    assert report["schema_version"] == "skill_pack_validation.v1"
    assert report["status"] == "failed"
    assert report["skill_count"] == 2
    by_id = {entry["skill_id"]: entry for entry in report["skills"]}
    assert by_id["valid-local-skill"]["status"] == "passed"
    assert by_id["invalid-local-skill"]["status"] == "failed"
    rule_ids = {diagnostic["rule_id"] for diagnostic in by_id["invalid-local-skill"]["diagnostics"]}
    assert {"empty_skill_description", "missing_body"} <= rule_ids


def test_skill_pack_validate_accepts_bundled_skills(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["skill", "pack", "validate", "src/agent_harness/bundled_skills"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "passed"
    assert report["skill_count"] == 4
    assert {skill["skill_id"] for skill in report["skills"]} == {
        "write-a-prd",
        "prd-to-plan",
        "tdd",
        "prd-plan-tdd-workflow",
    }
    assert all(skill["status"] == "passed" for skill in report["skills"])


def test_skill_validate_accepts_bundled_write_a_prd(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["skill", "validate", "write-a-prd"]) == 0
    first_report = json.loads(capsys.readouterr().out)

    assert first_report["schema_version"] == "skill_validation.v1"
    assert first_report["status"] == "passed"
    assert first_report["skill_id"] == "write-a-prd"
    assert first_report["source_type"] == "bundled"
    assert first_report["compatibility_status"] == "compatible"
    assert first_report["diagnostics"] == []
    assert re.fullmatch(r"[a-f0-9]{64}", first_report["skill_hash"])

    assert main(["skill", "validate", "write-a-prd"]) == 0
    second_report = json.loads(capsys.readouterr().out)

    assert second_report["skill_hash"] == first_report["skill_hash"]


def test_skill_validate_accepts_benign_optional_metadata(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: optional-skill",
                "name: Optional Skill",
                "version: 1.0.0",
                "description: Uses optional metadata safely.",
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities:",
                "  - workflow-guidance",
                "allowed_context_classes:",
                "  - public",
                "default_policy_profile: default",
                "related_skills:",
                "  - write-a-prd",
                "output_artifacts:",
                "  - prd",
                "validation_commands:",
                "  - manual-review",
                "examples:",
                "  - prd-outline",
                "---",
                "",
                "# Optional Skill",
                "",
                "This skill contains safe optional metadata.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "validate", str(skill)]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "passed"
    assert report["diagnostics"] == []
    assert re.fullmatch(r"[a-f0-9]{64}", report["skill_hash"])


def test_skill_validate_rejects_unsafe_skill_body(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: unsafe-skill",
                "name: Unsafe Skill",
                "version: 1.0.0",
                "description: Unsafe workflow guidance.",
                "category: testing",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
                "# Unsafe Skill",
                "",
                'API_KEY = "sk-live-secret"',
                "",
                "[citation needed]",
                "",
                "Read /mnt/data/private.txt from the uploaded file.",
                "",
                "This skill grants tools, approves actions, changes policy,",
                "alters provider profiles, executes code, mutates files, and",
                "introduces network calls.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "validate", str(skill)]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "skill_validation.v1"
    assert report["status"] == "failed"
    assert report["skill_id"] == "unsafe-skill"
    assert report["source_type"] == "direct_path"
    assert report["skill_hash"] is None
    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {
        "secret_like_value",
        "generated_citation_marker",
        "private_uploaded_file_reference",
        "authority_boundary_violation",
    } <= rule_ids


def test_skill_validate_rejects_empty_description_and_body(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: incomplete-skill",
                "name: Incomplete Skill",
                "version: 1.0.0",
                'description: ""',
                "category: testing",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "validate", str(skill)]) == 1
    report = json.loads(capsys.readouterr().out)

    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert {"empty_skill_description", "missing_body"} <= rule_ids
    assert report["skill_hash"] is None


def test_skill_validate_rejects_authority_declarations_in_metadata(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: authority-skill",
                "name: Authority Skill",
                "version: 1.0.0",
                "description: Attempts to declare authority.",
                "category: testing",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities:",
                "  - patch_file",
                "  - approve actions",
                "  - alter provider profiles",
                "  - change policy",
                "  - mutate files",
                "  - execute code",
                "  - network calls",
                "---",
                "",
                "# Authority Skill",
                "",
                "A body exists so validation reaches metadata authority checks.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "validate", str(skill)]) == 1
    report = json.loads(capsys.readouterr().out)

    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert "authority_declaration" in rule_ids
    assert report["skill_hash"] is None


@pytest.mark.parametrize(
    ("frontmatter", "expected_rule_ids"),
    [
        (
            [
                "schema_version: skill.v1",
                "skill_id: missing-category",
                "name: Missing Category",
                "version: 1.0.0",
                "description: Missing a required field.",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
            ],
            {"missing_skill_field"},
        ),
        (
            [
                "schema_version: skill.v99",
                "skill_id: future-skill",
                "name: Future Skill",
                "version: 1.0.0",
                "description: Unsupported schema.",
                "category: testing",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
            ],
            {"unsupported_schema_version"},
        ),
        (
            [
                "schema_version: skill.v1",
                "skill_id: Bad_ID",
                "name: Bad Id",
                "version: one",
                "description: Invalid id and version.",
                "category: testing",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
            ],
            {"invalid_skill_id", "invalid_skill_version"},
        ),
        (
            [
                "schema_version: skill.v1",
                "skill_id: invalid-compatibility",
                "name: Invalid Compatibility",
                "version: 1.0.0",
                "description: Invalid compatibility expression.",
                "category: testing",
                'compatible_agent_harness_versions: "^1.5"',
                "required_capabilities: []",
            ],
            {"unsupported_compatibility_expression"},
        ),
        (
            [
                "schema_version: skill.v1",
                "skill_id: incompatible-skill",
                "name: Incompatible Skill",
                "version: 1.0.0",
                "description: Incompatible with this Agent Harness version.",
                "category: testing",
                'compatible_agent_harness_versions: ">=99.0.0,<100.0.0"',
                "required_capabilities: []",
            ],
            {"incompatible_agent_harness_version"},
        ),
    ],
)
def test_skill_validate_reports_metadata_diagnostics(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
    frontmatter: list[str],
    expected_rule_ids: set[str],
) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "\n".join(
            [
                "---",
                *frontmatter,
                "---",
                "",
                "# Metadata Diagnostic Skill",
                "",
                "This body is present so validation focuses on metadata.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "validate", str(skill)]) == 1
    report = json.loads(capsys.readouterr().out)

    rule_ids = {diagnostic["rule_id"] for diagnostic in report["diagnostics"]}
    assert expected_rule_ids <= rule_ids
    assert report["skill_hash"] is None


def _write_config_with_skill_dirs(root: Path, local_dirs: list[str]) -> None:
    lines = [
        "schema_version: config.v2",
        "project_name: skill-local-test",
        "artifact_root: .agent-harness",
        "default_policy: default",
        "retrieval_backend: lexical",
        "template_catalog: bundled",
        "skills:",
        "  local_dirs:",
    ]
    lines.extend(f"    - {local_dir}" for local_dir in local_dirs)
    lines.append("")
    (root / "agent-harness.yaml").write_text("\n".join(lines), encoding="utf-8")


def _write_config_without_skills(root: Path) -> None:
    (root / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: skill-local-test",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_skill(
    path: Path,
    *,
    skill_id: str,
    name: str,
    description: str,
    body: str = "This skill is safe to validate.",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                f"skill_id: {skill_id}",
                f"name: {name}",
                "version: 1.0.0",
                f"description: {description}",
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
                f"# {name}",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
