from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY


def test_deterministic_dense_index_can_be_built_and_queried_without_optional_dependencies(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _hide_optional_retrieval_dependencies(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "# Alpha\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    (docs / "beta.md").write_text(
        "# Beta\n\nunrelated release notes\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "dense-demo",
                "--paths",
                "docs",
                "--mode",
                "dense",
                "--dense-backend",
                "deterministic",
            ]
        )
        == 0
    )
    build = json.loads(capsys.readouterr().out)
    assert build["backend"] == "dense"
    assert build["embedding_backend"] == "deterministic"
    assert build["embedding_model"] == "token-set"
    assert build["embedding_model_version"] == "baseline"
    assert build["remote_embeddings"] is False

    assert (
        main(
            [
                "retrieval",
                "query",
                "dense-demo",
                "--query",
                "config loader policy",
                "--mode",
                "dense",
                "--k",
                "2",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)

    assert result["schema_version"] == "retrieval_query.v1"
    assert result["index_id"] == "dense-demo"
    assert result["mode"] == "dense"
    assert result["retrieval"]["schema_version"] == "retrieval_backend.v2"
    assert result["retrieval"]["requested_backend"] == "dense"
    assert result["retrieval"]["active_backend"] == "deterministic_dense"
    assert result["retrieval"]["backend"] == "deterministic"
    assert result["retrieval"]["embedding_model"] == "token-set"
    assert result["retrieval"]["embedding_model_version"] == "baseline"
    assert result["retrieval"]["remote_embeddings"] is False
    assert result["results"][0]["path"] == "docs/alpha.md"
    assert result["results"][0]["retrieval_method"] == "dense"
    assert set(result["results"][0]["scores"]) == {"dense"}
    assert result["results"][0]["scores"]["dense"] > 0
    assert result["results"][0]["provenance"] == [
        {"method": "dense", "score": result["results"][0]["scores"]["dense"]}
    ]


def test_hybrid_query_merges_duplicate_lexical_and_dense_results(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _hide_optional_retrieval_dependencies(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "both.md").write_text(
        "# Both\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    (docs / "other.md").write_text(
        "# Other\n\nunrelated release notes\n",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "hybrid-demo",
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

    assert (
        main(
            [
                "retrieval",
                "query",
                "hybrid-demo",
                "--query",
                "config loader policy",
                "--mode",
                "hybrid",
                "--k",
                "5",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)

    paths = [item["path"] for item in result["results"]]
    assert paths.count("docs/both.md") == 1
    item = result["results"][0]
    assert item["path"] == "docs/both.md"
    assert item["retrieval_method"] == "both"
    assert set(item["scores"]) == {"lexical", "dense"}
    assert item["scores"]["lexical"] > item["scores"]["dense"] > 0
    assert {entry["method"] for entry in item["provenance"]} == {"lexical", "dense"}
    assert result["retrieval"]["requested_backend"] == "hybrid"
    assert result["retrieval"]["active_backend"] == "deterministic_hybrid"
    assert result["retrieval"]["remote_embeddings"] is False


def test_deterministic_dense_query_results_are_stable_after_rebuild(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _hide_optional_retrieval_dependencies(monkeypatch)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "# Alpha\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    build_args = [
        "retrieval",
        "index",
        "build",
        "--index-id",
        "dense-demo",
        "--paths",
        "docs",
        "--mode",
        "dense",
        "--dense-backend",
        "deterministic",
    ]
    query_args = [
        "retrieval",
        "query",
        "dense-demo",
        "--query",
        "config loader policy",
        "--mode",
        "dense",
        "--k",
        "5",
    ]
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T14:00:00Z")
    assert main(build_args) == 0
    capsys.readouterr()
    assert main(query_args) == 0
    first = json.loads(capsys.readouterr().out)

    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T14:00:00Z")
    assert main([*build_args, "--overwrite"]) == 0
    capsys.readouterr()
    assert main(query_args) == 0
    second = json.loads(capsys.readouterr().out)

    assert second == first


def _seed_project(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(DEFAULT_POLICY, indent=2),
        encoding="utf-8",
    )


def _hide_optional_retrieval_dependencies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, package: str | None = None):  # type: ignore[no-untyped-def]
        if name in {"qdrant_client", "fastembed"}:
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
