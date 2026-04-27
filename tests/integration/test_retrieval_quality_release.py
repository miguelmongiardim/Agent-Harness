from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_harness.cli import main


def test_release_readiness_reports_retrieval_demo_and_rejects_remote_defaults(
    tmp_path: Path,
    monkeypatch,
    capsys,  # type: ignore[no-untyped-def]
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    _write_minimal_release_project(tmp_path)
    shutil.copytree(
        repo_root / "examples" / "retrieval_quality",
        tmp_path / "examples" / "retrieval_quality",
        ignore=shutil.ignore_patterns(".agent-harness"),
    )
    scorecards = tmp_path / ".agent-harness" / "retrieval-scorecards"
    scorecards.mkdir(parents=True)
    (scorecards / "demo-retrieval.json").write_text(
        json.dumps(
            {
                "schema_version": "retrieval_scorecard.v1",
                "status": "passed",
                "index_id": "demo-retrieval",
            }
        ),
        encoding="utf-8",
    )

    assert main(["release", "readiness"]) == 0
    readiness = json.loads(capsys.readouterr().out)

    assert readiness["retrieval"]["demo"]["status"] == "passed"
    assert readiness["retrieval"]["demo"]["path"] == "examples/retrieval_quality"
    assert readiness["retrieval"]["configuration"]["status"] == "passed"
    assert readiness["retrieval"]["configuration"]["remote_defaults"] == []

    (tmp_path / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: remote-retrieval-default",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "retrieval:",
                "  default_mode: dense",
                "  dense:",
                "    embedding_backend: fastembed",
                "    remote_embeddings: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["release", "readiness"]) == 0
    remote = json.loads(capsys.readouterr().out)

    assert remote["retrieval"]["configuration"]["status"] == "failed"
    assert remote["retrieval"]["configuration"]["remote_defaults"] == [
        {
            "path": "agent-harness.yaml",
            "setting": "retrieval.dense.remote_embeddings",
            "value": True,
        }
    ]
    assert "retrieval.configuration" in {diagnostic["gate"] for diagnostic in remote["diagnostics"]}


def _write_minimal_release_project(root: Path) -> None:
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
    docs = root / "docs"
    docs.mkdir()
    (docs / "prd-agent-harness-v3.md").write_text(
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
    (docs / "migration.md").write_text(
        "# Schema Migration\n\nv0.3.0 to v1.0.0 public compatibility baseline.\n",
        encoding="utf-8",
    )
    (docs / "release-readiness.md").write_text(
        "\n".join(
            [
                "# Release Readiness",
                "",
                "## Release Checklist",
                "",
                "Run checks.",
                "",
                "## Tag Process",
                "",
                "Tag after verification.",
                "",
                "## Artifact Verification",
                "",
                "Verify artifacts.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [9.9.9] - 2026-04-27\n\n- Release.\n",
        encoding="utf-8",
    )
