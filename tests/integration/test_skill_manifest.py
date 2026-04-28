from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_harness.cli import main
from agent_harness.evals import run_eval_spec
from agent_harness.schemas import EvalSpec
from tests.conftest import seed_project


def test_skill_manifest_is_linked_and_inspectable_for_skill_dry_run(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-skill-manifest")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T22:00:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "skill-manifest",
                "title": "Skill manifest",
                "intent": "Record selected skill provenance as a run artifact.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]

    assert summary["artifacts"]["skill_manifest"].endswith("skill_manifest.json")
    manifest = json.loads((run_dir / "skill_manifest.json").read_text(encoding="utf-8"))
    artifact_index = json.loads((run_dir / "artifact-index.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "skill_manifest.v1"
    assert manifest["run_id"] == "run-skill-manifest"
    assert manifest["task_id"] == "skill-manifest"
    assert manifest["context_manifest_id"]
    assert len(manifest["skills"]) == 1

    record = manifest["skills"][0]
    assert record["skill_id"] == "prd-plan-tdd-workflow"
    assert record["version"] == "1.0.0"
    assert record["source_type"] == "bundled"
    assert record["source"] == "bundled_skills/prd-plan-tdd-workflow/SKILL.md"
    assert record["skill_hash"]
    assert record["requested_by"] == [
        {
            "kind": "task",
            "reference": "task.json",
            "field": "skills",
            "required": True,
        }
    ]
    assert record["resolution_time"]
    assert record["resolution_status"] == "resolved"
    assert record["inclusion_status"] == "included"
    assert record["policy_decision_id"]
    assert record["context_manifest_id"] == manifest["context_manifest_id"]
    assert record["context_manifest_item_id"]

    assert artifact_index["artifacts"]["skill_manifest"] == summary["artifacts"]["skill_manifest"]
    assert artifact_index["artifact_hashes"]["skill_manifest"]

    assert main(["inspect", "run", summary["run_id"]]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["skill_manifest"] == manifest


def test_run_without_skills_does_not_emit_skill_manifest(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-no-skill-manifest")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T22:05:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "no-skill-manifest",
                "title": "No skill manifest",
                "intent": "Run without selected skills.",
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]

    assert "skill_manifest" not in summary["artifacts"]
    assert not (run_dir / "skill_manifest.json").exists()

    assert main(["inspect", "run", summary["run_id"]]) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert "skill_manifest" not in inspect_payload


def test_skill_manifest_records_equivalent_provenance_for_dry_and_non_dry_runs(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T22:10:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "equivalent-skill-manifest",
                "title": "Equivalent skill manifest",
                "intent": "Record skill provenance on both execution paths.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-skill-manifest-dry")
    assert main(["run", str(task), "--dry-run"]) == 0
    dry_summary = json.loads(capsys.readouterr().out)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-skill-manifest-full")
    assert main(["run", str(task)]) == 0
    full_summary = json.loads(capsys.readouterr().out)

    dry_manifest = _read_skill_manifest(tmp_path, dry_summary["run_id"])
    full_manifest = _read_skill_manifest(tmp_path, full_summary["run_id"])
    dry_record = dry_manifest["skills"][0]
    full_record = full_manifest["skills"][0]

    comparable_fields = {
        "skill_id",
        "version",
        "source_type",
        "source",
        "skill_hash",
        "requested_by",
        "resolution_time",
        "resolution_status",
        "inclusion_status",
    }
    assert {field: dry_record[field] for field in comparable_fields} == {
        field: full_record[field] for field in comparable_fields
    }
    assert dry_record["context_manifest_id"] == dry_manifest["context_manifest_id"]
    assert full_record["context_manifest_id"] == full_manifest["context_manifest_id"]
    assert dry_record["policy_decision_id"]
    assert full_record["policy_decision_id"]


def test_security_blocked_run_with_skills_does_not_claim_skill_inclusion(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-security-blocked-skill")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T22:15:00Z")
    (tmp_path / "credentials.py").write_text('API_KEY = "not-a-real-key"\n', encoding="utf-8")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "security-blocked-skill",
                "title": "Security blocked skill",
                "intent": "Stop before context assembly when security blocks the run.",
                "skills": ["prd-plan-tdd-workflow"],
                "target_paths": ["credentials.py"],
                "allowed_tools": ["read_file"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]

    assert summary["status"] == "failed"
    assert "security_findings" in summary["artifacts"]
    assert "context_manifest" not in summary["artifacts"]
    assert "skill_manifest" not in summary["artifacts"]
    assert not (run_dir / "context_manifest.json").exists()
    assert not (run_dir / "skill_manifest.json").exists()


def test_eval_spec_can_verify_expected_skill_usage(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-eval-skill-manifest")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T22:20:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "eval-skill-manifest",
                "title": "Eval skill manifest",
                "intent": "Let an eval verify selected skill usage.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )
    spec = EvalSpec(
        schema_version="eval.v1",
        eval_id="expected-skill-usage",
        title="Expected skill usage",
        task_path="task.json",
        expected_status="dry_run",
        required_artifacts=["context_manifest", "skill_manifest", "summary"],
        expected_skills=["prd-plan-tdd-workflow"],
    )

    result = run_eval_spec(tmp_path, spec)

    assert result.passed is True
    assert result.artifacts["skill_manifest"].endswith("skill_manifest.json")
    invariant = next(item for item in result.invariants if item.name == "expected_skills_used")
    assert invariant.passed is True


def _read_skill_manifest(root: Path, run_id: str) -> dict[str, Any]:
    run_dir = root / ".agent-harness" / "runs" / run_id
    return json.loads((run_dir / "skill_manifest.json").read_text(encoding="utf-8"))
