from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.templates.schema import TemplateSpec
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


def test_template_catalog_exposes_required_bundled_v7_packs(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["template", "list"]) == 0
    rows = {
        parts[0]: parts
        for line in capsys.readouterr().out.splitlines()
        if (parts := line.split("\t"))
    }
    required = {
        "python-lib",
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "retrieval-quality",
    }

    assert set(rows) == required

    for template_id in sorted(required):
        assert rows[template_id][3:] == ["bundled_pack", "compatible"]
        assert main(["template", "show", template_id]) == 0
        detail = json.loads(capsys.readouterr().out)

        assert detail["source_type"] == "bundled_pack"
        assert detail["bundle_path"] == f"bundled_templates/{template_id}/template.v2.toml"
        assert detail["template_schema_version"] == "template.v2"
        assert detail["minimum_agent_harness_version"]
        assert detail["required_capabilities"]
        assert detail["generated_schema_versions"]["template"] == "template.v2"
        assert detail["provider_requirements"]
        assert detail["policy_requirements"]["required_template_capabilities"]
        assert detail["retrieval_assumptions"]["remote_embeddings"] is False
        assert detail["eval_or_demo_metadata"]["commands"]
        files = {file["path"]: file["content"] for file in detail["files"]}
        assert "README.md" in files
        schemas = {
            json.loads(content)["schema_version"]
            for path, content in files.items()
            if path.startswith("examples/") and path.endswith(".json")
        }
        assert {"config.v2", "policy.v2", "task.v2", "eval.v1"} <= schemas


def test_template_show_reads_python_lib_pack_manifest_metadata(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["template", "show", "python-lib"]) == 0
    detail = json.loads(capsys.readouterr().out)

    assert detail["source_type"] == "bundled_pack"
    assert detail["compatibility_status"] == "compatible"
    assert detail["bundle_path"] == "bundled_templates/python-lib/template.v2.toml"
    assert detail["parameters"]["package_name"]["type"] == "path_fragment"
    assert detail["generated_schema_versions"] == {
        "config": "config.v2",
        "policy": "policy.v2",
        "task": "task.v2",
        "template": "template.v2",
    }
    assert detail["required_capabilities"] == ["python.library"]
    assert detail["eval_or_demo_metadata"]["commands"] == ["python -m pytest"]
    assert {file["path"] for file in detail["files"]} == {
        "README.md",
        "examples/agent-harness.config.json",
        "examples/default.policy.json",
        "examples/python-lib.eval.json",
        "examples/python-lib.task.json",
        "pyproject.toml",
        "src/example_python_lib/__init__.py",
        "src/example_python_lib/core.py",
        "tests/test_core.py",
    }


def test_template_list_reports_pack_sources_for_migrated_python_trio(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    assert main(["template", "list"]) == 0
    rows = {
        parts[0]: parts
        for line in capsys.readouterr().out.splitlines()
        if (parts := line.split("\t"))
    }

    assert rows["python-lib"] == [
        "python-lib",
        "1.0.0",
        "Python Library",
        "bundled_pack",
        "compatible",
    ]
    assert rows["cli-tool"] == [
        "cli-tool",
        "1.0.0",
        "CLI Tool",
        "bundled_pack",
        "compatible",
    ]

    assert main(["template", "show", "cli-tool"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["source_type"] == "bundled_pack"
    assert detail["compatibility_status"] == "compatible"
    assert detail["bundle_path"] == "bundled_templates/cli-tool/template.v2.toml"
    assert detail["parameters"] == {}
    assert detail["files"]


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
    assert set(results) == {
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    }

    for template_id, result in results.items():
        assert result["listed"] is True
        assert result["shown"] is True
        assert result["status"] == "passed"
        assert result["apply"]["status"] == "completed"
        assert result["apply"]["approvals"] == []
        scaffold = tmp_path / result["apply"]["destination"]
        assert scaffold.parts[-1] == "scaffold"
        assert (scaffold / "README.md").exists(), template_id
        example_schemas = {
            json.loads(path.read_text(encoding="utf-8"))["schema_version"]
            for path in (scaffold / "examples").glob("*.json")
        }
        assert {"config.v2", "policy.v2", "task.v2", "eval.v1"} <= example_schemas

    evidence_path = (
        tmp_path / ".agent-harness" / "release" / "evidence" / "template-validation.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "passed"
    assert {entry["template_id"] for entry in evidence["templates"]} == set(results)


def test_required_bundled_v7_packs_dry_run_without_mutation(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    required = [
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    ]

    for template_id in required:
        target = tmp_path / "preview" / template_id
        assert (
            main(
                [
                    "template",
                    "apply",
                    template_id,
                    "--target",
                    str(target),
                    "--dry-run",
                ]
            )
            == 0
        )
        evidence = json.loads(capsys.readouterr().out)

        assert evidence["status"] == "planned"
        assert evidence["mode"] == "dry_run"
        assert evidence["template_id"] == template_id
        assert evidence["source"]["source_type"] == "bundled_pack"
        assert evidence["planned_creates"]
        assert evidence["approval_required"] is False
        assert not target.exists()

    assert not (tmp_path / ".agent-harness").exists()


def test_required_bundled_v7_packs_do_not_claim_remote_pack_features(
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    forbidden_claims = {
        "remote catalog",
        "marketplace",
        "cloud registry",
        "template hook",
        "template script",
        "signing",
    }
    for template_id in (
        "cli-tool",
        "fastapi-service",
        "provider-audit",
        "python-lib",
        "retrieval-quality",
    ):
        assert main(["template", "show", template_id]) == 0
        detail = json.loads(capsys.readouterr().out)
        searchable = json.dumps(detail, sort_keys=True).lower()

        assert not any(claim in searchable for claim in forbidden_claims)
        assert detail["retrieval_assumptions"]["remote_embeddings"] is False


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
