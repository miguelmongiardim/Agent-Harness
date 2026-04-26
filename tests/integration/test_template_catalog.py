from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.schemas import TemplateSpec
from tests.conftest import seed_project


def test_template_v1_bundle_remains_readable() -> None:
    spec = TemplateSpec.model_validate(
        {
            "schema_version": "template.v1",
            "name": "legacy-python-lib",
            "description": "Legacy v1 template fixture.",
            "files": [
                {
                    "path": "README.md",
                    "content": "# Legacy\n",
                }
            ],
        }
    )

    assert spec.schema_version == "template.v1"
    assert spec.required_capabilities == []
    assert spec.generated_schema_versions == {}


def test_template_catalog_exposes_python_trio_with_v2_metadata(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["template", "list"]) == 0
    listed = capsys.readouterr().out.splitlines()

    assert any(line.startswith("python-lib\t") for line in listed)
    assert any(line.startswith("cli-tool\t") for line in listed)
    assert any(line.startswith("fastapi-service\t") for line in listed)

    for template_id in ("python-lib", "cli-tool", "fastapi-service"):
        assert main(["template", "show", template_id]) == 0
        detail = json.loads(capsys.readouterr().out)

        assert detail["template_schema_version"] == "template.v2"
        assert detail["minimum_agent_harness_version"]
        assert detail["required_capabilities"]
        assert detail["generated_schema_versions"]["template"] == "template.v2"
        assert detail["provider_requirements"]
        assert detail["policy_requirements"]["required_template_capabilities"]
        assert detail["retrieval_assumptions"]["remote_embeddings"] is False
        assert detail["eval_or_demo_metadata"]


def test_template_validate_all_applies_bundled_templates_cleanly_and_records_release_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T11:00:00Z")

    assert main(["template", "validate", "--all"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "template_validation.v1"
    assert report["status"] == "passed"
    results = {entry["template_id"]: entry for entry in report["templates"]}
    assert set(results) == {"cli-tool", "fastapi-service", "python-lib"}

    for template_id, result in results.items():
        assert result["listed"] is True
        assert result["shown"] is True
        assert result["status"] == "passed"
        assert result["apply"]["status"] == "completed"
        assert result["apply"]["approvals"] == []
        scaffold = tmp_path / result["apply"]["destination"]
        assert scaffold.parts[-1] == "scaffold"
        assert (scaffold / "pyproject.toml").exists(), template_id

    evidence_path = (
        tmp_path / ".agent-harness" / "release" / "evidence" / "template-validation.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert {entry["template_id"] for entry in evidence["templates"]} == set(results)


def test_template_docs_cover_validation_and_clean_apply_boundaries() -> None:
    docs = Path("docs/templates.md").read_text(encoding="utf-8")

    assert "agent-harness template validate --all" in docs
    assert "Clean empty-destination scaffolding does not require approval" in docs
    assert "non-empty destination" in docs
    assert "--force" in docs


def test_incompatible_template_v2_rejects_before_write_planning(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    restrictive_policy = dict(DEFAULT_POLICY)
    restrictive_policy["template_capabilities"] = {
        "allowed_capabilities": [],
        "default_action": "deny",
    }
    (tmp_path / "policies" / "deny-templates.json").write_text(
        json.dumps(restrictive_policy, indent=2), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "template-incompatible-run")

    destination = tmp_path / "scaffold"

    assert (
        main(
            [
                "template",
                "apply",
                "python-lib",
                "--destination",
                str(destination),
                "--profile",
                "deny-templates",
            ]
        )
        == 1
    )
    result = capsys.readouterr()
    assert "unsupported template capabilities: python.library" in result.err

    assert not (destination / "pyproject.toml").exists()
    assert not (tmp_path / ".agent-harness" / "runs" / "template-incompatible-run").exists()
