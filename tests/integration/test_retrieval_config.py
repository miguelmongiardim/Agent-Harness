from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from agent_harness.context.retrieval import ingest_documents
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.policy import PolicyEngine
from agent_harness.policy.schema import PolicyProfile
from tests.integration.test_retrieval_hardening import _hide_optional_retrieval_dependencies


def test_valid_v120_local_first_retrieval_config_validates(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "hybrid",
                "dense": {
                    "embedding_backend": "fastembed",
                    "embedding_provider": "fastembed",
                    "remote_embeddings": False,
                },
                "qdrant": {
                    "backend": "qdrant-local",
                },
                "fallback": {
                    "allow_lexical": True,
                },
            },
        },
    )

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out

    assert "OK config: agent-harness.yaml artifact_root=.agent-harness" in output


def test_valid_v120_local_first_yaml_retrieval_config_validates(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: test-project",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "retrieval:",
                "  default_mode: hybrid",
                "  dense:",
                "    embedding_backend: fastembed",
                "    embedding_provider: fastembed",
                "    remote_embeddings: false",
                "  qdrant:",
                "    backend: qdrant-local",
                "  fallback:",
                "    allow_lexical: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_policy(tmp_path)

    assert main(["doctor"]) == 0
    output = capsys.readouterr().out

    assert "OK config: agent-harness.yaml artifact_root=.agent-harness" in output


def test_remote_embeddings_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "dense": {
                    "embedding_backend": "fastembed",
                    "remote_embeddings": True,
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids remote_embeddings: true" in captured.err
    assert "retrieval.dense.remote_embeddings" in captured.err


def test_hosted_embedding_provider_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "dense": {
                    "embedding_provider": "openai",
                    "remote_embeddings": False,
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids hosted embedding providers" in captured.err
    assert "retrieval.dense.embedding_provider" in captured.err


def test_cloud_qdrant_url_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "qdrant": {
                    "backend": "qdrant-server",
                    "url": "https://demo.us-east.aws.cloud.qdrant.io",
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids cloud Qdrant URLs" in captured.err
    assert "retrieval.qdrant.url" in captured.err


def test_api_key_backed_qdrant_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "qdrant": {
                    "backend": "qdrant-server",
                    "url": "http://localhost:6333",
                    "api_key_env": "QDRANT_API_KEY",
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids API-key-backed Qdrant endpoints" in captured.err
    assert "retrieval.qdrant.api_key_env" in captured.err


def test_https_qdrant_url_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "qdrant": {
                    "backend": "qdrant-server",
                    "url": "https://qdrant.example.test:6333",
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids remote HTTPS Qdrant endpoints" in captured.err
    assert "retrieval.qdrant.url" in captured.err


@pytest.mark.parametrize("url", ["http://10.1.2.3:6333", "http://203.0.113.10:6333"])
def test_non_loopback_qdrant_url_config_fails_with_v120_validation_error(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
    url: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "dense",
                "qdrant": {
                    "backend": "qdrant-server",
                    "url": url,
                },
            },
        },
    )

    assert main(["doctor"]) == 2
    captured = capsys.readouterr()

    assert "v1.2.0 local-first retrieval forbids non-loopback Qdrant endpoints" in captured.err
    assert "retrieval.qdrant.url" in captured.err


def test_v120_retrieval_config_falls_back_to_lexical_when_dense_dependencies_are_missing(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(
        tmp_path,
        {
            "retrieval": {
                "default_mode": "hybrid",
                "dense": {
                    "embedding_backend": "fastembed",
                    "remote_embeddings": False,
                },
                "qdrant": {
                    "backend": "qdrant-local",
                },
                "fallback": {
                    "allow_lexical": True,
                },
            },
        },
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text(
        "# Guide\n\nadd_numbers refactor guidance\n",
        encoding="utf-8",
    )
    ingest_documents(
        tmp_path,
        tmp_path / ".agent-harness",
        ["docs"],
        PolicyEngine(tmp_path, PolicyProfile.model_validate(DEFAULT_POLICY)),
    )
    task_path = _write_task(tmp_path, "v120-missing-dense-deps")
    _hide_optional_retrieval_dependencies(monkeypatch)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_RUN_ID", "run-v120-missing-dense-deps")
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T13:00:00Z")

    assert main(["run", str(task_path), "--dry-run"]) == 0
    capsys.readouterr()
    manifest = json.loads(
        (
            tmp_path
            / ".agent-harness"
            / "runs"
            / "run-v120-missing-dense-deps"
            / "context_manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["retrieval"]["schema_version"] == "retrieval_backend.v2"
    assert manifest["retrieval"]["requested_backend"] == "qdrant"
    assert manifest["retrieval"]["active_backend"] == "lexical"
    assert manifest["retrieval"]["fallback_status"] == "used"
    assert manifest["retrieval"]["fallback_reason"] == "missing_optional_dependencies"
    assert manifest["retrieval"]["diagnostics"] == [
        "qdrant-client and fastembed are unavailable; lexical fallback active"
    ]
    assert manifest["retrieval"]["remote_embeddings"] is False


def _write_config(root: Path, updates: dict[str, object]) -> None:
    config: dict[str, object] = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
    }
    config.update(updates)
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    _write_policy(root)


def _write_policy(root: Path) -> None:
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def _write_task(root: Path, task_id: str) -> Path:
    path = root / "task.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "task.v2",
                "task_id": task_id,
                "title": "Retrieve docs",
                "intent": "Inspect retrieval context without changing files.",
                "context_queries": ["add_numbers"],
                "allowed_tools": [],
                "max_steps": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
