from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent_harness.cli import main
from agent_harness.context.qdrant_local import optional_qdrant_local_dependencies_available
from agent_harness.defaults import DEFAULT_POLICY


def test_retrieval_scorecard_compares_lexical_dense_and_hybrid_modes(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs" / "public"
    docs.mkdir(parents=True)
    (docs / "config.md").write_text(
        "# Config\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    (docs / "tests.md").write_text(
        "# Tests\n\nprecision recall tests for retrieval scorecards\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "scorecard.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard_fixture.v1",
                "queries": [
                    {
                        "query_id": "config-policy",
                        "query": "config loader policy",
                        "expected_chunks": ["docs/public/config.md"],
                        "allowed_sensitivities": ["public"],
                    },
                    {
                        "query_id": "quality-metrics",
                        "query": "precision recall tests",
                        "expected_chunks": ["docs/public/tests.md"],
                        "allowed_sensitivities": ["public"],
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "quality-demo",
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
                "scorecard",
                str(fixture_path),
                "--index-id",
                "quality-demo",
                "--k",
                "1",
            ]
        )
        == 0
    )
    scorecard = json.loads(capsys.readouterr().out)

    assert scorecard["schema_version"] == "retrieval_scorecard.v1"
    assert scorecard["status"] == "passed"
    assert scorecard["index_id"] == "quality-demo"
    assert scorecard["k"] == 1
    assert scorecard["compared_modes"] == ["lexical", "dense", "hybrid"]
    assert (tmp_path / scorecard["scorecard_path"]).exists()
    assert {
        row["mode"]: (row["precision_at_k"], row["recall_at_k"], row["status"])
        for row in scorecard["backend_comparison"]
    } == {
        "lexical": (1.0, 1.0, "passed"),
        "dense": (1.0, 1.0, "passed"),
        "hybrid": (1.0, 1.0, "passed"),
    }

    queries = {query["query_id"]: query for query in scorecard["queries"]}
    lexical = queries["config-policy"]["modes"]["lexical"]
    assert lexical["expected_chunks"] == ["docs/public/config.md"]
    assert lexical["hit_chunks"] == ["docs/public/config.md"]
    assert lexical["missed_chunks"] == []
    assert lexical["unexpected_chunks"] == []
    assert lexical["precision_at_k"] == 1.0
    assert lexical["recall_at_k"] == 1.0
    assert lexical["results"][0]["path"] == "docs/public/config.md"
    assert lexical["results"][0]["sensitivity"] == "public"
    assert "text" not in lexical["results"][0]


def test_release_readiness_reports_passing_retrieval_scorecard_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    _write_release_metadata(tmp_path)
    docs = tmp_path / "docs" / "public"
    docs.mkdir(exist_ok=True)
    (docs / "config.md").write_text(
        "# Config\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "scorecard.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard_fixture.v1",
                "queries": [
                    {
                        "query_id": "config-policy",
                        "query": "config loader policy",
                        "expected_chunks": ["docs/public/config.md"],
                        "allowed_sensitivities": ["public"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "quality-demo",
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
                "scorecard",
                str(fixture_path),
                "--index-id",
                "quality-demo",
                "--k",
                "1",
            ]
        )
        == 0
    )
    scorecard = json.loads(capsys.readouterr().out)

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)

    assert readiness["retrieval"]["scorecard"]["status"] == "passed"
    assert readiness["retrieval"]["scorecard"]["schema_version"] == "retrieval_scorecard.v1"
    assert readiness["retrieval"]["scorecard"]["evidence"] == scorecard["scorecard_path"]
    assert readiness["retrieval"]["scorecard"]["index_id"] == "quality-demo"


@pytest.mark.retrieval_optional
def test_qdrant_local_retrieval_scorecard_smoke_is_opt_in(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    if not optional_qdrant_local_dependencies_available():
        pytest.skip("install agent-harness[retrieval] to run qdrant-local scorecard smoke")
    if os.environ.get("AGENT_HARNESS_RUN_RETRIEVAL_OPTIONAL_TESTS") != "1":
        pytest.skip("set AGENT_HARNESS_RUN_RETRIEVAL_OPTIONAL_TESTS=1 for local model smoke")
    monkeypatch.chdir(tmp_path)
    _seed_project(tmp_path)
    docs = tmp_path / "docs" / "public"
    docs.mkdir(parents=True)
    (docs / "config.md").write_text(
        "# Config\n\nconfig loader policy refactor guidance\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "scorecard.json"
    fixture_path.write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard_fixture.v1",
                "queries": [
                    {
                        "query_id": "config-policy",
                        "query": "config loader policy",
                        "expected_chunks": ["docs/public/config.md"],
                        "allowed_sensitivities": ["public"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "retrieval",
                "index",
                "build",
                "--index-id",
                "qdrant-scorecard",
                "--paths",
                "docs",
                "--mode",
                "hybrid",
                "--dense-backend",
                "qdrant-local",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "retrieval",
                "scorecard",
                str(fixture_path),
                "--index-id",
                "qdrant-scorecard",
                "--k",
                "1",
            ]
        )
        == 0
    )
    scorecard = json.loads(capsys.readouterr().out)
    assert scorecard["status"] == "passed"
    assert scorecard["metrics"]["dense"]["status"] == "passed"
    assert scorecard["queries"][0]["modes"]["dense"]["retrieval"]["backend"] == "qdrant-local"


def _seed_project(root: Path) -> None:
    config = {
        "schema_version": "config.v2",
        "project_name": "test-project",
        "artifact_root": ".agent-harness",
        "default_policy": "default",
        "retrieval_backend": "lexical",
        "template_catalog": "bundled",
    }
    policy = {
        **DEFAULT_POLICY,
        "sensitivity_rules": [
            {"pattern": "docs/public/**", "classification": "public"},
            *DEFAULT_POLICY["sensitivity_rules"],
        ],
    }
    (root / "agent-harness.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text(
        json.dumps(policy, indent=2),
        encoding="utf-8",
    )


def _write_release_metadata(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "agent-harness"',
                'version = "9.9.9"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Agent Harness",
                "",
                "## What This Repo Proves",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## Roadmap / Not Enabled By Init",
                "",
                "Roadmap features remain future scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "prd-agent-harness-v3.md").write_text(
        "\n".join(
            [
                "# Agent Harness V3 / v1.0.0 PRD",
                "",
                "Agent Harness V3 is the v1.0.0 maturity release.",
                "",
                "## Compatibility And Deprecation Policy",
                "",
                "V2 schemas are the v1.0.0 public baseline.",
                "",
                "## Implemented vs Roadmap",
                "",
                "Implemented capabilities are separate from roadmap scope.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "migration.md").write_text(
        "\n".join(
            [
                "# Schema Migration",
                "",
                "## Migration Notes From v0.3.0 To v1.0.0",
                "",
                "v1.0.0 keeps the v0.3.0 V2 schemas as the public baseline.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "release-readiness.md").write_text(
        "\n".join(
            [
                "# Release Readiness",
                "",
                "## Release Checklist",
                "",
                "Run package, demo, template, docs, artifact, tag, and CI checks.",
                "",
                "## Tag Process",
                "",
                "Create and push the release tag only after final verification.",
                "",
                "## Artifact Verification",
                "",
                "Verify wheel and source distribution hashes before release.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [9.9.9] - 2026-04-27\n\n- Release.\n",
        encoding="utf-8",
    )
