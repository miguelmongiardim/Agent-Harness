from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY


def test_migrate_schemas_reports_without_mutating_legacy_workspace(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    inputs = _write_legacy_workspace(tmp_path)
    before = {path: path.read_text(encoding="utf-8") for path in inputs}

    assert main(["migrate", "schemas"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "schema_migration_report.v1"
    assert report["mode"] == "report"
    assert report["write_enabled"] is False

    records = {record["path"]: record for record in report["records"]}
    assert set(records) == {
        "agent-harness.yaml",
        "policies/default.json",
        "task.json",
        "templates/example.json",
    }
    assert records["agent-harness.yaml"]["original_schema_version"] == "config.v1"
    assert records["agent-harness.yaml"]["effective_schema_version"] == "config.v2"
    assert "schema_version" in records["agent-harness.yaml"]["changed_fields"]
    assert records["task.json"]["original_schema_version"] == "task.v1"
    assert records["task.json"]["effective_schema_version"] == "task.v2"
    assert records["policies/default.json"]["original_schema_version"] == "policy.v1"
    assert records["policies/default.json"]["effective_schema_version"] == "policy.v2"
    assert records["templates/example.json"]["original_schema_version"] == "template.v1"
    assert records["templates/example.json"]["unsupported_upgrade_reasons"]

    for record in records.values():
        assert record["written"] is False
        assert isinstance(record["unchanged_fields"], list)
        assert isinstance(record["warnings"], list)

    assert {path: path.read_text(encoding="utf-8") for path in inputs} == before


def test_migrate_schemas_write_updates_safe_inputs_and_reports_skips(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _write_legacy_workspace(tmp_path)

    assert main(["migrate", "schemas", "--write"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["mode"] == "write"
    records = {record["path"]: record for record in report["records"]}
    assert records["agent-harness.yaml"]["written"] is True
    assert records["task.json"]["written"] is True
    assert records["policies/default.json"]["written"] is True
    assert records["templates/example.json"]["written"] is False
    assert records["templates/example.json"]["unsupported_upgrade_reasons"]

    assert "schema_version: config.v2" in (tmp_path / "agent-harness.yaml").read_text(
        encoding="utf-8"
    )
    assert json.loads((tmp_path / "task.json").read_text(encoding="utf-8"))[
        "schema_version"
    ] == "task.v2"
    assert json.loads((tmp_path / "policies" / "default.json").read_text(encoding="utf-8"))[
        "schema_version"
    ] == "policy.v2"
    assert json.loads((tmp_path / "templates" / "example.json").read_text(encoding="utf-8"))[
        "schema_version"
    ] == "template.v1"


def test_migrate_schemas_write_preserves_stricter_legacy_policy(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    policy = _flat_legacy_policy()
    policy["provider_input_policy"]["internal"] = "deny"
    policy["provider_input_policy"]["generated"] = "deny"
    _write_legacy_workspace(tmp_path, policy=policy)

    assert main(["migrate", "schemas", "--write"]) == 0
    capsys.readouterr()

    assert main(["inspect", "policy", "default"]) == 0
    migrated = json.loads(capsys.readouterr().out)
    assert migrated["schema_version"] == "policy.v2"
    assert migrated["provider_input"]["rules"]["internal"] == "deny"
    assert migrated["provider_input"]["rules"]["generated"] == "deny"
    assert migrated["provider_input_policy"]["internal"] == "deny"
    assert migrated["provider_input_policy"]["generated"] == "deny"


def test_migrate_schemas_report_can_be_stored_as_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    _write_legacy_workspace(tmp_path)
    output = Path(".agent-harness") / "migrations" / "schema-migration-report.json"

    assert main(["migrate", "schemas", "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)
    stored = json.loads((tmp_path / output).read_text(encoding="utf-8"))

    assert report["artifact"] == ".agent-harness/migrations/schema-migration-report.json"
    assert stored == report
    assert stored["mode"] == "report"
    assert stored["records"]


def _write_legacy_workspace(root: Path, policy: dict[str, object] | None = None) -> list[Path]:
    config_path = root / "agent-harness.yaml"
    config_path.write_text(
        "\n".join(
            [
                "schema_version: config.v1",
                "project_name: legacy-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "",
            ]
        ),
        encoding="utf-8",
    )

    if policy is None:
        policy = dict(DEFAULT_POLICY)
        policy["schema_version"] = "policy.v1"
    policy_path = root / "policies" / "default.json"
    policy_path.parent.mkdir()
    policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    task_path = root / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "legacy-task",
                "title": "Inspect legacy target",
                "intent": "Inspect without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    template_path = root / "templates" / "example.json"
    template_path.parent.mkdir()
    template_path.write_text(
        json.dumps(
            {
                "schema_version": "template.v1",
                "name": "example",
                "description": "Legacy local template",
                "files": [{"path": "README.md", "content": "# Example\n"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return [config_path, policy_path, task_path, template_path]


def _flat_legacy_policy() -> dict[str, object]:
    policy = deepcopy(DEFAULT_POLICY)
    policy["schema_version"] = "policy.v1"
    for key in (
        "trust_zones",
        "provider_input",
        "approvals",
        "scanner",
        "template_capabilities",
        "migration",
        "profile_kind",
        "documented",
        "deliberate_selection_required",
    ):
        policy.pop(key)
    return policy
