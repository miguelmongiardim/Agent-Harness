from __future__ import annotations

import json
import re
from pathlib import Path

from agent_harness.cli import main
from tests.conftest import seed_project


def test_skill_resolve_records_task_requested_skill(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    task = tmp_path / "task.yaml"
    task.write_text(
        "\n".join(
            [
                "schema_version: task.v2",
                "task_id: skill-guided-task",
                "title: Skill guided task",
                "intent: Resolve requested skill guidance.",
                "allowed_tools:",
                "  - read_file",
                "skills:",
                "  - prd-plan-tdd-workflow",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "resolve", "--task", str(task)]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "skill_resolution.v1"
    assert report["status"] == "passed"
    assert report["task_id"] == "skill-guided-task"
    assert report["task_path"] == "task.yaml"
    assert report["diagnostics"] == []
    assert report["authority"]["policy_profile"] == "default"
    assert report["authority"]["provider_profile"] is None
    assert report["authority"]["allowed_tools"] == ["read_file"]
    assert report["authority"]["tool_changes"] == []
    assert report["authority"]["approval_changes"] == []
    assert report["authority"]["policy_changes"] == []
    assert report["authority"]["provider_changes"] == []

    records = {skill["skill_id"]: skill for skill in report["skills"]}
    resolved = records["prd-plan-tdd-workflow"]
    assert resolved["resolution_status"] == "resolved"
    assert resolved["required"] is True
    assert resolved["version"] == "1.0.0"
    assert resolved["source_type"] == "bundled"
    assert resolved["source"] == "bundled_skills/prd-plan-tdd-workflow/SKILL.md"
    assert re.fullmatch(r"[a-f0-9]{64}", resolved["skill_hash"])
    assert resolved["requested_by"] == [
        {
            "kind": "task",
            "reference": "task.yaml",
            "field": "skills",
            "required": True,
        }
    ]
    assert resolved["diagnostics"] == []


def test_skill_resolve_fails_for_unknown_task_requested_skill(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    task = tmp_path / "task.yaml"
    task.write_text(
        "\n".join(
            [
                "schema_version: task.v2",
                "task_id: unknown-skill-task",
                "title: Unknown skill task",
                "intent: Resolve an unknown requested skill.",
                "skills:",
                "  - missing-skill",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "resolve", "--task", str(task)]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["status"] == "failed"
    assert report["diagnostics"][0]["rule_id"] == "unknown_skill"
    assert report["skills"] == [
        {
            "skill_id": "missing-skill",
            "resolution_status": "missing",
            "required": True,
            "requested_by": [
                {
                    "kind": "task",
                    "reference": "task.yaml",
                    "field": "skills",
                    "required": True,
                }
            ],
            "version": None,
            "source_type": None,
            "source": None,
            "compatibility_status": None,
            "validation_status": None,
            "skill_hash": None,
            "diagnostics": [
                {
                    "rule_id": "unknown_skill",
                    "severity": "error",
                    "message": "skill not found: missing-skill",
                    "location": "skills",
                }
            ],
        }
    ]


def test_task_v2_accepts_skills(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "task-v2-skills",
                "title": "Task v0.3.0 Skills",
                "intent": "Validate task-requested skills.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(task)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["skills"] == ["prd-plan-tdd-workflow"]


def test_skill_resolve_fails_for_invalid_task_requested_skill(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    _write_invalid_local_skill(tmp_path / "skills" / "invalid-local" / "SKILL.md")
    task = tmp_path / "task.yaml"
    task.write_text(
        "\n".join(
            [
                "schema_version: task.v2",
                "task_id: invalid-skill-task",
                "title: Invalid skill task",
                "intent: Resolve an invalid requested skill.",
                "skills:",
                "  - invalid-local",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "resolve", "--task", str(task)]) == 1
    report = json.loads(capsys.readouterr().out)
    invalid = report["skills"][0]

    assert report["status"] == "failed"
    assert invalid["resolution_status"] == "invalid"
    assert invalid["required"] is True
    assert invalid["source_type"] == "local"
    assert invalid["source"] == "skills/invalid-local/SKILL.md"
    assert {diagnostic["rule_id"] for diagnostic in invalid["diagnostics"]} == {
        "empty_skill_description",
        "missing_body",
    }
    assert {diagnostic["rule_id"] for diagnostic in report["diagnostics"]} == {
        "empty_skill_description",
        "missing_body",
    }


def test_task_v1_rejects_skills_explicitly(
    tmp_path: Path,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    task = tmp_path / "legacy-task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "legacy-skills",
                "title": "Legacy task",
                "intent": "A legacy task cannot request skills.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(task)]) == 2
    assert "task.v1 does not support skills" in capsys.readouterr().err


def test_template_recommended_skills_are_recorded_and_non_required(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    _write_config_with_template_dirs(tmp_path, ["local-templates"])
    _write_guided_template_pack(
        tmp_path / "local-templates" / "guided-pack",
        recommended_skills=["prd-plan-tdd-workflow", "missing-recommended-skill"],
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "guided-template-apply")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T20:00:00Z")

    assert main(["template", "show", "guided-pack"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["recommended_skills"] == [
        "prd-plan-tdd-workflow",
        "missing-recommended-skill",
    ]

    assert main(["template", "apply", "guided-pack", "--target", str(tmp_path / "scaffold")]) == 0
    summary = json.loads(capsys.readouterr().out)
    evidence = json.loads(
        (tmp_path / summary["artifacts"]["template_application"]).read_text(encoding="utf-8")
    )
    assert evidence["recommended_skills"] == [
        "prd-plan-tdd-workflow",
        "missing-recommended-skill",
    ]
    workspace = json.loads(
        (tmp_path / ".agent-harness" / "workspace.json").read_text(encoding="utf-8")
    )
    recommendations = workspace["skill_recommendations"]
    assert {recommendation["skill_id"] for recommendation in recommendations} == {
        "prd-plan-tdd-workflow",
        "missing-recommended-skill",
    }
    for recommendation in recommendations:
        assert recommendation["template_id"] == "guided-pack"
        assert recommendation["template_version"] == "1.0.0"
        assert recommendation["destination"] == "scaffold"
        assert recommendation["run_id"] == "guided-template-apply"
        assert recommendation["evidence"] == summary["artifacts"]["template_application"]
        assert recommendation["recorded_at"] == "2026-04-28T20:00:00Z"

    task = tmp_path / "task.yaml"
    task.write_text(
        "\n".join(
            [
                "schema_version: task.v2",
                "task_id: recommendation-only-task",
                "title: Recommendation only task",
                "intent: Template recommendations should not force usage.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["skill", "resolve", "--task", str(task)]) == 0
    report = json.loads(capsys.readouterr().out)
    records = {skill["skill_id"]: skill for skill in report["skills"]}

    assert report["status"] == "passed"
    assert {diagnostic["rule_id"] for diagnostic in report["diagnostics"]} == {
        "missing_recommended_skill"
    }
    assert records["prd-plan-tdd-workflow"]["resolution_status"] == "resolved"
    assert records["prd-plan-tdd-workflow"]["required"] is False
    assert records["prd-plan-tdd-workflow"]["requested_by"] == [
        {
            "kind": "template",
            "reference": "guided-pack@1.0.0",
            "field": "recommended_skills",
            "required": False,
        }
    ]
    assert records["missing-recommended-skill"]["resolution_status"] == "missing"
    assert records["missing-recommended-skill"]["required"] is False
    assert records["missing-recommended-skill"]["diagnostics"][0]["rule_id"] == (
        "missing_recommended_skill"
    )


def _write_config_with_skill_dirs(root: Path, local_dirs: list[str]) -> None:
    lines = [
        "schema_version: config.v2",
        "project_name: skill-resolution-test",
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


def _write_config_with_template_dirs(root: Path, local_dirs: list[str]) -> None:
    lines = [
        "schema_version: config.v2",
        "project_name: skill-resolution-test",
        "artifact_root: .agent-harness",
        "default_policy: default",
        "retrieval_backend: lexical",
        "template_catalog: bundled",
        "templates:",
        "  local_dirs:",
    ]
    lines.extend(f"    - {local_dir}" for local_dir in local_dirs)
    lines.append("")
    (root / "agent-harness.yaml").write_text("\n".join(lines), encoding="utf-8")


def _write_invalid_local_skill(path: Path) -> None:
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: invalid-local",
                "name: Invalid Local",
                "version: 1.0.0",
                "description: \"\"",
                "category: planning",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_guided_template_pack(pack: Path, *, recommended_skills: list[str]) -> None:
    pack.mkdir(parents=True)
    recommended = ", ".join(f'"{skill_id}"' for skill_id in recommended_skills)
    (pack / "template.v2.toml").write_text(
        f"""
schema_version = "template.v2"
template_id = "guided-pack"
version = "1.0.0"
title = "Guided Pack"
description = "Local template pack with skill recommendations."
minimum_agent_harness_version = "0.2.0"
required_capabilities = ["python.library"]
recommended_skills = [{recommended}]

[parameters.package_name]
type = "path_fragment"
default = "guided_pkg"
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
path = "README.md"
source = "files/README.md"
""".lstrip(),
        encoding="utf-8",
    )
    source = pack / "files" / "README.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Guided Pack\n", encoding="utf-8")
