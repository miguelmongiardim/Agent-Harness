from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY
from tests.conftest import seed_project


def test_task_requested_skill_enters_context_manifest_with_policy_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    seed_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-skill-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T21:00:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "skill-context",
                "title": "Skill context",
                "intent": "Include selected workflow guidance in context.",
                "skills": ["prd-plan-tdd-workflow"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]
    manifest = json.loads((run_dir / "context_manifest.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    skill_items = [
        item
        for item in manifest["items"]
        if item["source_kind"] == "skill" and item["skill_id"] == "prd-plan-tdd-workflow"
    ]
    assert len(skill_items) == 1
    item = skill_items[0]
    assert item["skill_version"] == "1.0.0"
    assert item["skill_source"] == "bundled_skills/prd-plan-tdd-workflow/SKILL.md"
    assert item["skill_hash"]
    assert item["content_hash"] == item["skill_hash"]
    assert item["inclusion_mode"] == "task_required"
    assert item["policy_allowed"] is True
    assert item["policy_decision_id"]
    assert "PRD Plan TDD Workflow" in item["text"]
    assert manifest["rejected_items"] == []

    skill_decisions = [
        event["payload"]
        for event in events
        if event["type"] == "policy_decision"
        and event["payload"].get("operation") == "skill_context"
    ]
    assert skill_decisions == [
        {
            "operation": "skill_context",
            "skill_id": "prd-plan-tdd-workflow",
            "source": "bundled_skills/prd-plan-tdd-workflow/SKILL.md",
            "decision": next(
                event["payload"]["decision"]
                for event in events
                if event["payload"].get("decision", {}).get("decision_id")
                == item["policy_decision_id"]
            ),
        }
    ]


def test_rejected_skill_context_does_not_persist_body_text(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    _write_config_with_skill_dirs(tmp_path, ["skills"])
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8"
    )
    _write_local_skill(
        tmp_path / "skills" / "local-guidance" / "SKILL.md",
        allowed_context_classes=["public"],
        body="LOCAL SKILL BODY SHOULD NOT LEAK",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-rejected-skill-context")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T21:05:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "rejected-skill-context",
                "title": "Rejected skill context",
                "intent": "Reject local guidance that cannot enter internal context.",
                "skills": ["local-guidance"],
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]
    manifest_text = (run_dir / "context_manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)

    assert "LOCAL SKILL BODY SHOULD NOT LEAK" not in manifest_text
    assert manifest["items"] == []
    assert len(manifest["rejected_items"]) == 1
    rejected = manifest["rejected_items"][0]
    assert rejected["source_kind"] == "skill"
    assert rejected["skill_id"] == "local-guidance"
    assert rejected["skill_source"] == "skills/local-guidance/SKILL.md"
    assert rejected["inclusion_mode"] == "task_required"
    assert rejected["sensitivity"] == "internal"
    assert rejected["text"] is None
    assert rejected["content_hash"] == rejected["skill_hash"]
    assert rejected["policy_allowed"] is False
    assert "skill context classes" in rejected["policy_reason"]


def test_provider_input_treats_accepted_skill_as_context_evidence(
    tmp_path: Path,
    monkeypatch,  # type: ignore[no-untyped-def]
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    _write_config_with_mock_provider(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-skill-provider-input")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T21:10:00Z")
    task = tmp_path / "task.json"
    task.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "skill-provider-input",
                "title": "Skill provider input",
                "intent": "Send accepted skill guidance as provider evidence.",
                "skills": ["prd-plan-tdd-workflow"],
                "max_steps": 1,
            }
        ),
        encoding="utf-8",
    )

    assert main(["run", str(task), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    run_dir = tmp_path / ".agent-harness" / "runs" / summary["run_id"]
    manifest = json.loads((run_dir / "context_manifest.json").read_text(encoding="utf-8"))
    provider_input = json.loads((run_dir / "provider_input.json").read_text(encoding="utf-8"))

    skill_item = next(item for item in manifest["items"] if item["source_kind"] == "skill")
    record = provider_input["records"][0]
    assert record["manifest_item_id"] == skill_item["item_id"]
    assert record["path"] == "bundled_skills/prd-plan-tdd-workflow/SKILL.md"
    assert record["sensitivity"] == "public"
    assert record["policy_action"] == "allow"
    assert record["included"] is True
    assert record["content_hash"] == skill_item["skill_hash"]
    assert "PRD Plan TDD Workflow" in record["text"]

    persisted_task = json.loads((run_dir / "task.json").read_text(encoding="utf-8"))
    persisted_policy = json.loads((run_dir / "policy.json").read_text(encoding="utf-8"))
    assert persisted_task["skills"] == ["prd-plan-tdd-workflow"]
    assert persisted_task["allowed_tools"] is None
    assert persisted_policy["allowed_tools"] == DEFAULT_POLICY["allowed_tools"]


def _write_config_with_skill_dirs(root: Path, local_dirs: list[str]) -> None:
    lines = [
        "schema_version: config.v2",
        "project_name: skill-context-test",
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


def _write_config_with_mock_provider(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "skill-context-test",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
        "default_provider_profile": "mock-default",
        "provider_profiles": [
            {
                "provider_profile_id": "mock-default",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic",
                "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
                "network": False,
                "requires_approval": False,
            }
        ],
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2), encoding="utf-8"
    )


def _write_local_skill(
    path: Path,
    *,
    allowed_context_classes: list[str],
    body: str,
) -> None:
    path.parent.mkdir(parents=True)
    classes = "\n".join(f"  - {context_class}" for context_class in allowed_context_classes)
    path.write_text(
        "\n".join(
            [
                "---",
                "schema_version: skill.v1",
                "skill_id: local-guidance",
                "name: Local Guidance",
                "version: 1.0.0",
                "description: Local workflow guidance.",
                "category: workflow",
                'compatible_agent_harness_versions: ">=1.4.0,<2.0.0"',
                "required_capabilities: []",
                "allowed_context_classes:",
                classes,
                "---",
                "",
                "# Local Guidance",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )
