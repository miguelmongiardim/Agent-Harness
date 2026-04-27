from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY


def test_hybrid_retrieval_index_context_filters_policy_and_records_provenance(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    _write_policy(tmp_path, "default", DEFAULT_POLICY)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "both.md").write_text(
        "# Both\n\nconfig loader policy shared guidance\n",
        encoding="utf-8",
    )
    (docs / "lexical.md").write_text(
        "# Lexical\n\nconfiguration notes\n",
        encoding="utf-8",
    )
    (docs / "private.md").write_text(
        "# Private\n\nconfig loader policy private denied notes\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "context-demo",
                "--paths",
                "docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "deterministic",
            ]
        )
        == 0
    )
    capsys.readouterr()

    _write_config(
        tmp_path,
        retrieval={
            "index_id": "context-demo",
            "default_mode": "hybrid",
            "dense": {
                "embedding_backend": "deterministic",
                "remote_embeddings": False,
            },
        },
        provider=True,
    )
    restrictive = dict(DEFAULT_POLICY)
    restrictive["name"] = "retrieval-runtime"
    restrictive["deny_globs"] = [*DEFAULT_POLICY["deny_globs"], "docs/private.md"]
    _write_policy(tmp_path, "retrieval-runtime", restrictive)
    task_path = _write_task(tmp_path, "retrieval-runtime")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-retrieval-runtime")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T15:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / "run-retrieval-runtime" / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == "context_manifest.v2"
    assert manifest["retrieval"]["schema_version"] == "retrieval_backend.v2"
    assert manifest["retrieval"]["requested_backend"] == "hybrid"
    assert manifest["retrieval"]["active_backend"] == "deterministic_hybrid"
    assert manifest["retrieval"]["backend"] == "deterministic"
    assert manifest["retrieval"]["embedding_model"] == "token-set"
    assert manifest["retrieval"]["embedding_model_version"] == "baseline"
    assert manifest["retrieval"]["index_id"] == "context-demo"
    assert manifest["retrieval"]["index_path"] == (
        ".agent-harness/indexes/context-demo/documents.jsonl"
    )
    assert manifest["retrieval"]["remote_embeddings"] is False

    included_by_path = {item["path"]: item for item in manifest["items"]}
    assert set(included_by_path) == {"docs/both.md", "docs/lexical.md"}
    assert included_by_path["docs/both.md"]["retrieval_method"] == "both"
    assert set(included_by_path["docs/both.md"]["scores"]) == {"lexical", "dense"}
    assert {entry["method"] for entry in included_by_path["docs/both.md"]["provenance"]} == {
        "lexical",
        "dense",
    }
    assert included_by_path["docs/lexical.md"]["retrieval_method"] == "lexical"
    assert set(included_by_path["docs/lexical.md"]["scores"]) == {"lexical"}

    rejected_by_path = {item["path"]: item for item in manifest["rejected_items"]}
    assert set(rejected_by_path) == {"docs/private.md"}
    assert rejected_by_path["docs/private.md"]["policy_allowed"] is False
    assert rejected_by_path["docs/private.md"]["policy_reason"].startswith("path denied by glob")
    assert rejected_by_path["docs/private.md"]["retrieval_method"] == "both"
    assert set(rejected_by_path["docs/private.md"]["scores"]) == {"lexical", "dense"}
    assert rejected_by_path["docs/private.md"]["text"] is None
    assert "private denied notes" not in json.dumps(manifest)

    provider_input = json.loads(
        (
            tmp_path / ".agent-harness" / "runs" / "run-retrieval-runtime" / "provider_input.json"
        ).read_text(encoding="utf-8")
    )
    records_by_path = {record["path"]: record for record in provider_input["records"]}
    assert set(records_by_path) == set(included_by_path)
    assert "docs/private.md" not in records_by_path
    assert {record["manifest_item_id"] for record in records_by_path.values()} == {
        item["item_id"] for item in included_by_path.values()
    }


def test_retrieved_hard_denied_sensitivity_is_rejected_before_context_acceptance(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path)
    _write_policy(tmp_path, "default", DEFAULT_POLICY)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "internal.md").write_text(
        "# Internal\n\nconfig loader policy credential note\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "sensitivity-demo",
                "--paths",
                "docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "deterministic",
            ]
        )
        == 0
    )
    capsys.readouterr()

    _write_config(
        tmp_path,
        retrieval={
            "index_id": "sensitivity-demo",
            "default_mode": "hybrid",
            "dense": {
                "embedding_backend": "deterministic",
                "remote_embeddings": False,
            },
        },
    )
    sensitive = dict(DEFAULT_POLICY)
    sensitive["name"] = "retrieval-sensitive"
    sensitive["sensitivity_rules"] = [
        *DEFAULT_POLICY["sensitivity_rules"],
        {"pattern": "docs/internal.md", "classification": "secret"},
    ]
    _write_policy(tmp_path, "retrieval-sensitive", sensitive)
    task_path = _write_task(tmp_path, "retrieval-sensitive")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-retrieval-sensitive")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T15:15:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-retrieval-sensitive"
            / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["items"] == []
    rejected_by_path = {item["path"]: item for item in manifest["rejected_items"]}
    assert set(rejected_by_path) == {"docs/internal.md"}
    rejected = rejected_by_path["docs/internal.md"]
    assert rejected["sensitivity"] == "secret"
    assert rejected["policy_allowed"] is False
    assert rejected["policy_reason"] == "secret is hard-denied for context"
    assert rejected["retrieval_method"] == "both"
    assert rejected["text"] is None
    assert "credential note" not in json.dumps(manifest)


def _write_config(
    root: Path,
    *,
    retrieval: dict[str, object] | None = None,
    provider: bool = False,
) -> None:
    config: dict[str, object] = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
    }
    if retrieval is not None:
        config["retrieval"] = retrieval
    if provider:
        config["default_provider_profile"] = "mock-default"
        config["provider_profiles"] = [
            {
                "provider_profile_id": "mock-default",
                "transport": "mock",
                "trust_zone": "mock",
                "model": "deterministic",
                "endpoint_env": "AGENT_HARNESS_MOCK_ENDPOINT",
                "network": False,
                "requires_approval": False,
            }
        ]
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")


def _write_policy(root: Path, name: str, policy: dict[str, object]) -> None:
    policies = root / "policies"
    policies.mkdir(exist_ok=True)
    (policies / f"{name}.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")


def _write_task(root: Path, policy_profile: str) -> Path:
    path = root / "task.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": "retrieval-runtime",
                "title": "Assemble context from a retrieval index",
                "intent": "Inspect retrieval context without changing files.",
                "policy_profile": policy_profile,
                "context_queries": ["config loader policy"],
                "allowed_tools": [],
                "max_steps": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
