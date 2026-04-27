from __future__ import annotations

import json
from pathlib import Path

from agent_harness.cli import main
from agent_harness.defaults import DEFAULT_POLICY


def test_retrieval_index_build_writes_lexical_manifest(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T14:00:00Z")
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guide\n\nadd_numbers refactor policy guidance\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "lexical-demo",
                "--paths",
                "docs",
                "--mode",
                "lexical",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    manifest_path = tmp_path / summary["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert summary["schema_version"] == "retrieval_index.v1"
    assert summary["index_id"] == "lexical-demo"
    assert summary["backend"] == "lexical"
    assert manifest["schema_version"] == "retrieval_index.v1"
    assert manifest["index_id"] == "lexical-demo"
    assert manifest["backend"] == "lexical"
    assert manifest["remote_embeddings"] is False
    assert manifest["source_paths"] == ["docs/guide.md"]
    assert set(manifest["source_hashes"]) == {"docs/guide.md"}
    assert manifest["chunking_config"] == {"max_chars": 1200}
    assert manifest["chunks"][0]["path"] == "docs/guide.md"
    assert (
        manifest["chunks"][0]["content_hash"]
        == manifest["chunk_hashes"][manifest["chunks"][0]["chunk_id"]]
    )
    assert (tmp_path / manifest["index_path"]).exists()


def test_retrieval_index_list_shows_created_lexical_index(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "lexical-demo",
                "--paths",
                "docs",
                "--mode",
                "lexical",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["retrieval", "index", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)

    assert listed == {
        "indexes": [
            {
                "index_id": "lexical-demo",
                "backend": "lexical",
                "source_count": 1,
                "chunk_count": 1,
                "manifest_path": ".agent-harness/indexes/lexical-demo/retrieval_index.json",
            }
        ]
    }


def test_retrieval_index_show_displays_reproducibility_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "lexical-demo",
                "--paths",
                "docs",
                "--mode",
                "lexical",
            ]
        )
        == 0
    )
    build_summary = json.loads(capsys.readouterr().out)

    assert main(["retrieval", "index", "show", "lexical-demo"]) == 0
    shown = json.loads(capsys.readouterr().out)

    assert shown["schema_version"] == "retrieval_index.v1"
    assert shown["index_id"] == "lexical-demo"
    assert shown["backend"] == "lexical"
    assert shown["source_hashes"] == build_summary["source_hashes"]
    assert shown["chunk_hashes"] == build_summary["chunk_hashes"]
    assert shown["chunking_config"] == {"max_chars": 1200}
    assert shown["retrieval_config_hash"] == build_summary["retrieval_config_hash"]
    assert shown["index_path"] == build_summary["index_path"]
    assert shown["qdrant_collection"] is None


def test_retrieval_index_delete_removes_manifest_and_storage(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "lexical-demo",
                "--paths",
                "docs",
                "--mode",
                "lexical",
            ]
        )
        == 0
    )
    capsys.readouterr()
    index_dir = tmp_path / ".agent-harness" / "indexes" / "lexical-demo"
    assert index_dir.exists()

    assert main(["retrieval", "index", "delete", "lexical-demo"]) == 0
    deleted = json.loads(capsys.readouterr().out)
    assert deleted == {"deleted": "lexical-demo"}
    assert not index_dir.exists()

    assert main(["retrieval", "index", "list"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed == {"indexes": []}


def test_retrieval_index_build_rejects_existing_index_without_overwrite(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")
    build_args = [
        "retrieval",
        "index",
        "build",
        "--index-id",
        "lexical-demo",
        "--paths",
        "docs",
        "--mode",
        "lexical",
    ]
    assert main(build_args) == 0
    capsys.readouterr()

    assert main(build_args) == 1
    captured = capsys.readouterr()

    assert "retrieval index already exists: lexical-demo" in captured.err


def test_retrieval_index_build_overwrite_replaces_existing_state(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    source.write_text("# Guide\n\nfirst policy retrieval\n", encoding="utf-8")
    build_args = [
        "retrieval",
        "index",
        "build",
        "--index-id",
        "lexical-demo",
        "--paths",
        "docs",
        "--mode",
        "lexical",
    ]
    assert main(build_args) == 0
    first = json.loads(capsys.readouterr().out)
    source.write_text("# Guide\n\nupdated policy retrieval\n", encoding="utf-8")

    assert main([*build_args, "--overwrite"]) == 0
    second = json.loads(capsys.readouterr().out)

    assert second["source_hashes"]["docs/guide.md"] != first["source_hashes"]["docs/guide.md"]
    assert (tmp_path / second["index_path"]).read_text(encoding="utf-8").count("\n") == 1


def test_retrieval_index_rebuild_preserves_stable_source_and_chunk_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\npolicy retrieval\n", encoding="utf-8")
    build_args = [
        "retrieval",
        "index",
        "build",
        "--index-id",
        "lexical-demo",
        "--paths",
        "docs",
        "--mode",
        "lexical",
    ]
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-27T14:00:00Z")
    assert main(build_args) == 0
    first = json.loads(capsys.readouterr().out)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-28T14:00:00Z")
    assert main([*build_args, "--overwrite"]) == 0
    second = json.loads(capsys.readouterr().out)

    assert second["created_at"] != first["created_at"]
    assert second["source_paths"] == first["source_paths"]
    assert second["source_hashes"] == first["source_hashes"]
    assert second["sources"] == first["sources"]
    assert second["chunk_ids"] == first["chunk_ids"]
    assert second["chunk_hashes"] == first["chunk_hashes"]
    assert second["chunks"] == first["chunks"]
    assert second["retrieval_config_hash"] == first["retrieval_config_hash"]


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
