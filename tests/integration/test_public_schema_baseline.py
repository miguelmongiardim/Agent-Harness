from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY


def test_init_run_and_inspect_emit_default_schema_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-public-schema-baseline")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T16:00:00Z")

    assert main(["init"]) == 0
    capsys.readouterr()
    assert "schema_version: config.v2" in (tmp_path / "agent-harness.yaml").read_text(
        encoding="utf-8"
    )
    default_policy = json.loads((tmp_path / "policies" / "default.json").read_text())
    assert default_policy["schema_version"] == "policy.v2"

    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "public-schema-baseline",
                "title": "Inspect current schema target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(task_path)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["schema_version"] == "task.v2"

    assert main(["run", str(task_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "dry_run"
    assert "schema_versions" in summary["artifacts"]

    assert main(["inspect", "run", "run-public-schema-baseline"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["schema_versions"] == {
        "config": {"original": "config.v2", "effective": "config.v2"},
        "task": {"original": "task.v2", "effective": "task.v2"},
        "policy": {"original": "policy.v2", "effective": "policy.v2"},
    }


def test_legacy_inputs_run_as_effective_current_schema_without_policy_widening(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-legacy-compatible-current")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T16:05:00Z")

    (tmp_path / "agent-harness.yaml").write_text(
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
    (tmp_path / "policies").mkdir()
    legacy_policy = dict(DEFAULT_POLICY)
    legacy_policy["schema_version"] = "policy.v1"
    (tmp_path / "policies" / "default.json").write_text(
        json.dumps(legacy_policy, indent=2), encoding="utf-8"
    )
    (tmp_path / ".agent-harness" / "runs").mkdir(parents=True)
    (tmp_path / ".agent-harness" / "indexes").mkdir(parents=True)

    target = tmp_path / "sample.py"
    target.write_text("def identity(value):\n    return value\n", encoding="utf-8")
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "schema_version": "task.v1",
                "task_id": "legacy-compatible-current",
                "title": "Inspect legacy target",
                "intent": "Inspect the target without changing files.",
                "target_paths": ["sample.py"],
                "allowed_tools": ["read_file"],
                "max_steps": 3,
            }
        ),
        encoding="utf-8",
    )

    assert main(["task", "validate", str(task_path)]) == 0
    validated = json.loads(capsys.readouterr().out)
    assert validated["schema_version"] == "task.v2"

    assert main(["run", str(task_path), "--dry-run"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "dry_run"

    assert main(["inspect", "run", "run-legacy-compatible-current"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["schema_versions"] == {
        "config": {"original": "config.v1", "effective": "config.v2"},
        "task": {"original": "task.v1", "effective": "task.v2"},
        "policy": {"original": "policy.v1", "effective": "policy.v2"},
    }

    policy_artifact = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-legacy-compatible-current"
            / "policy.json"
        ).read_text(encoding="utf-8")
    )
    assert policy_artifact["schema_version"] == "policy.v2"
    assert policy_artifact["provider_input_policy"] == legacy_policy["provider_input_policy"]
    assert policy_artifact["provider_trust_policy"] == legacy_policy["provider_trust_policy"]
    assert policy_artifact["security_fail_threshold"] == legacy_policy["security_fail_threshold"]


def test_bundled_task_examples_are_current_public_inputs(capsys) -> None:  # type: ignore[no-untyped-def]
    for task_path in sorted(Path("examples/tasks").glob("*.json")):
        raw = json.loads(task_path.read_text(encoding="utf-8"))
        assert raw["schema_version"] == "task.v2"

        assert main(["task", "validate", str(task_path)]) == 0
        validated = json.loads(capsys.readouterr().out)
        assert validated["schema_version"] == "task.v2"
