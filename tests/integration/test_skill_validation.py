from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from agent_harness.cli import main


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
                "description: \"\"",
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
