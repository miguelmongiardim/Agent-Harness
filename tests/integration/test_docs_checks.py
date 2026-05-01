from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_harness.cli import main
from tests.conftest import seed_project


def test_docs_check_fails_on_unsupported_claim_and_is_not_eval(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGENT_HARNESS_FIXED_TIME", "2026-04-26T17:00:00Z")
    seed_project(tmp_path)
    _write_eval_inputs(tmp_path)

    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "claim.md").write_text(
        "# Claim\n\nAgent Harness provides a web API.\n", encoding="utf-8"
    )

    assert main(["docs", "check"]) == 1
    docs_report = json.loads(capsys.readouterr().out)
    assert docs_report["status"] == "failed"
    unsupported = [
        finding
        for finding in docs_report["findings"]
        if finding["rule_id"] == "unsupported_doc_claim"
    ]
    assert unsupported
    assert unsupported[0]["path"] == "docs/claim.md"
    assert unsupported[0]["line"] == 3
    assert "web API" in unsupported[0]["text"]

    assert main(["eval"]) == 0
    eval_output = json.loads(capsys.readouterr().out)
    assert "scanner_report" not in eval_output
    assert not (tmp_path / ".agent-harness" / "exports" / "scanner-report.json").exists()


def test_docs_check_reports_required_sections_links_placeholders_schema_and_markdown(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "drift.md").write_text(
        "\n".join(
            [
                "# Drift",
                "",
                "Agent Harness supports deterministic workflows.",
                "",
                "Broken [internal link](missing.md).",
                "",
                "[citation needed]",
                "",
                "Schema `config.v99` is not real.",
                "",
                "Trailing whitespace here.  ",
                "",
                "### Jumped Heading",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}
    assert {
        "missing_implemented_vs_roadmap_sections",
        "broken_internal_link",
        "citation_placeholder",
        "schema_reference_drift",
        "markdown_trailing_whitespace",
        "markdown_heading_jump",
    } <= rule_ids


def test_docs_check_rejects_remote_retrieval_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "retrieval.md").write_text(
        "\n".join(
            [
                "# Retrieval",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness supports remote embeddings.",
                "",
                "## Roadmap",
                "",
                "Remote embeddings remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    retrieval_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_retrieval_scope_claim"
    ]

    assert retrieval_claims
    assert retrieval_claims[0]["path"] == "docs/retrieval.md"
    assert retrieval_claims[0]["line"] == 5
    assert "remote embeddings" in retrieval_claims[0]["text"]


def test_docs_check_allows_local_retrieval_scope_denials(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "retrieval.md").write_text(
        "\n".join(
            [
                "# Retrieval",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness supports local retrieval without remote embeddings.",
                "",
                "## Roadmap",
                "",
                "Remote embeddings remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"


def test_docs_check_rejects_hosted_operator_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "operator.md").write_text(
        "\n".join(
            [
                "# Operator",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness provides a hosted API.",
                "",
                "## Roadmap / Not implemented yet",
                "",
                "Hosted API support remains future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    operator_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_operator_scope_claim"
    ]

    assert operator_claims
    assert operator_claims[0]["path"] == "docs/operator.md"
    assert operator_claims[0]["line"] == 5
    assert "hosted API" in operator_claims[0]["text"]


def test_docs_check_rejects_remote_template_pack_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "templates.md").write_text(
        "\n".join(
            [
                "# Templates",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness provides a remote template catalog.",
                "",
                "## Roadmap / Not implemented yet",
                "",
                "Remote template catalogs remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    template_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_template_pack_scope_claim"
    ]

    assert template_claims
    assert template_claims[0]["path"] == "docs/templates.md"
    assert template_claims[0]["line"] == 5
    assert "remote template catalog" in template_claims[0]["text"]


def test_docs_check_rejects_remote_skill_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "skills.md").write_text(
        "\n".join(
            [
                "# Skills",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness provides a remote skill catalog.",
                "",
                "## Roadmap / Not implemented yet",
                "",
                "Remote skill catalogs remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    skill_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_skill_scope_claim"
    ]

    assert skill_claims
    assert skill_claims[0]["path"] == "docs/skills.md"
    assert skill_claims[0]["line"] == 5
    assert "remote skill catalog" in skill_claims[0]["text"]


@pytest.mark.parametrize(
    ("claim", "label"),
    [
        ("Agent Harness provides MCP tools.", "MCP tools"),
        ("Agent Harness supports write-capable MCP.", "write-capable MCP"),
        ("Agent Harness offers HTTP MCP.", "HTTP MCP"),
        ("Agent Harness includes a hosted MCP service.", "hosted MCP"),
        ("Agent Harness provides MCP runtime adapter behavior.", "MCP runtime adapter behavior"),
    ],
)
def test_docs_check_rejects_mcp_scope_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
    claim: str,
    label: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "mcp.md").write_text(
        "\n".join(
            [
                "# MCP",
                "",
                "## Current Capabilities",
                "",
                claim,
                "",
                "## Roadmap / Not implemented yet",
                "",
                f"{label} remains future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    mcp_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_mcp_scope_claim"
    ]

    assert mcp_claims
    assert mcp_claims[0]["path"] == "docs/mcp.md"
    assert mcp_claims[0]["line"] == 5
    assert label in mcp_claims[0]["text"]


@pytest.mark.parametrize(
    ("claim", "label"),
    [
        (
            "Agent Harness supports parallel multi-agent orchestration.",
            "parallel multi-agent orchestration",
        ),
        (
            "Agent Harness provides hosted multi-agent orchestration.",
            "hosted multi-agent orchestration",
        ),
        ("Agent Harness includes nested orchestration.", "nested orchestration"),
        (
            "Agent Harness offers MCP execution for multi-agent orchestration.",
            "MCP execution for multi-agent orchestration",
        ),
        (
            "Agent Harness supports enterprise multi-agent governance.",
            "enterprise multi-agent governance",
        ),
    ],
)
def test_docs_check_rejects_v11_orchestration_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
    claim: str,
    label: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "orchestration.md").write_text(
        "\n".join(
            [
                "# Orchestration",
                "",
                "## Current Capabilities",
                "",
                claim,
                "",
                "## Roadmap / Not implemented yet",
                "",
                f"{label} remains future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    orchestration_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_orchestration_scope_claim"
    ]

    assert orchestration_claims
    assert orchestration_claims[0]["path"] == "docs/orchestration.md"
    assert orchestration_claims[0]["line"] == 5
    assert {finding["line"] for finding in orchestration_claims} == {5}
    assert label in orchestration_claims[0]["text"]


@pytest.mark.parametrize(
    ("claim", "label"),
    [
        (
            "Agent Harness treats expanded multi-agent role chains as the "
            "preferred benchmark mode without comparison evidence.",
            "expanded multi-agent role chains",
        ),
        (
            "Agent Harness provides evidence-backed default role selection for "
            "planner, reviewer, and tester.",
            "evidence-backed default role selection",
        ),
    ],
)
def test_docs_check_rejects_benchmark_comparison_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
    claim: str,
    label: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "benchmark.md").write_text(
        "\n".join(
            [
                "# Benchmark",
                "",
                "## Current Capabilities",
                "",
                claim,
                "",
                "## Roadmap / Not implemented yet",
                "",
                "Benchmark comparison remains future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    comparison_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_benchmark_comparison_claim"
    ]

    assert comparison_claims
    assert comparison_claims[0]["path"] == "docs/benchmark.md"
    assert comparison_claims[0]["line"] == 5
    assert label in comparison_claims[0]["text"]


@pytest.mark.parametrize(
    ("claim", "label"),
    [
        ("Agent Harness provides hosted governance.", "hosted governance"),
        (
            "Agent Harness offers enterprise governance control planes.",
            "enterprise governance control planes",
        ),
        ("Agent Harness supports multi-tenant admin.", "multi-tenant admin"),
        ("Agent Harness provides compliance readiness.", "compliance readiness"),
        ("Agent Harness includes SOC2 readiness.", "SOC2 readiness"),
        ("Agent Harness offers ISO readiness.", "ISO readiness"),
        ("Agent Harness provides cloud deployment for governance.", "cloud deployment"),
        (
            "Agent Harness includes formal compliance certification.",
            "formal compliance certification",
        ),
    ],
)
def test_docs_check_rejects_v12_governance_compliance_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
    claim: str,
    label: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "governance.md").write_text(
        "\n".join(
            [
                "# Governance",
                "",
                "## Current Capabilities",
                "",
                claim,
                "",
                "## Roadmap / Not implemented yet",
                "",
                f"{label} remains future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    governance_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_governance_scope_claim"
    ]

    assert governance_claims
    assert governance_claims[0]["path"] == "docs/governance.md"
    assert governance_claims[0]["line"] == 5
    assert label in governance_claims[0]["text"]


@pytest.mark.parametrize(
    ("claim", "label"),
    [
        ("Agent Harness provides compliance-ready evidence packs.", "compliance-ready"),
        ("Agent Harness includes SOC2-ready evidence packs.", "SOC2-ready"),
        ("Agent Harness offers ISO-ready evidence packs.", "ISO-ready"),
        ("Agent Harness provides GDPR-compliant evidence packs.", "GDPR-compliant"),
        ("Agent Harness includes enterprise-certified evidence packs.", "enterprise-certified"),
        ("Agent Harness offers regulatory compliant evidence packs.", "regulatory compliant"),
        ("Agent Harness provides auditor-approved evidence packs.", "auditor-approved"),
        ("Agent Harness includes NIST compliant evidence packs.", "NIST compliant"),
        ("Agent Harness offers OWASP compliant evidence packs.", "OWASP compliant"),
    ],
)
def test_docs_check_rejects_v19_evidence_pack_compliance_claims_outside_roadmap(
    tmp_path: Path,
    monkeypatch,
    capsys,
    claim: str,
    label: str,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "evidence-pack.md").write_text(
        "\n".join(
            [
                "# Evidence Pack",
                "",
                "## Current Capabilities",
                "",
                claim,
                "",
                "## Roadmap / Not implemented yet",
                "",
                f"{label} evidence packs remain future-only.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    evidence_claims = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "unsupported_evidence_pack_claim"
    ]

    assert evidence_claims
    assert evidence_claims[0]["path"] == "docs/evidence-pack.md"
    assert evidence_claims[0]["line"] == 5
    assert label in evidence_claims[0]["text"]


def test_ci_runs_docs_check() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "python -m agent_harness docs check" in workflow


def test_v12_governance_report_and_export_scope_is_current_in_public_docs() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    roadmap = Path("docs/roadmap.md").read_text(encoding="utf-8")
    prd_link = "docs/prd-agent-harness-v12-local-governance-console.md"
    plan_link = "plans/agent-harness-v12-local-governance-console.md"

    assert prd_link in readme
    assert plan_link in readme
    assert "V12 local governance evidence surface" in readme
    assert "`agent-harness governance summary`" in readme
    assert "`agent-harness governance check`" in readme
    assert "agent-harness governance report --format markdown" in readme
    assert "agent-harness governance export --output .agent-harness/governance/" in readme
    assert "`governance_report.v1`" in readme
    assert "`governance_index.v1`" in readme
    assert "Operator API/UI and release-readiness gates" in readme
    assert "remain future-only" in readme
    assert "Compliance readiness and formal certification remain future-only." in readme

    assert "prd-agent-harness-v12-local-governance-console.md" in roadmap
    assert "agent-harness-v12-local-governance-console.md" in roadmap
    assert "v1.8.0 In Progress" in roadmap
    assert (
        "Phase 3 implements `agent-harness governance summary`, `check`, `report`, and" in roadmap
    )
    assert "`export`." in roadmap
    assert "`governance_report.v1`" in roadmap
    assert "`governance_index.v1`" in roadmap
    assert "compliance readiness, SOC2 readiness, ISO readiness" in roadmap
    assert "formal certification remain future-only." in roadmap


def test_v19_evidence_pack_scope_is_documented_without_implemented_claims() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    roadmap = Path("docs/roadmap.md").read_text(encoding="utf-8")
    evidence_docs = Path("docs/compliance-evidence-pack.md").read_text(encoding="utf-8")
    release_readiness = Path("docs/release-readiness.md").read_text(encoding="utf-8")
    operator_docs = Path("docs/operator-ui.md").read_text(encoding="utf-8")
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    security_model = Path("docs/security-model.md").read_text(encoding="utf-8")

    prd_link = "docs/prd-agent-harness-v1.9-compliance-evidence-pack.md"
    plan_link = "plans/agent-harness-v1.9-compliance-evidence-pack.md"

    assert prd_link in readme
    assert plan_link in readme
    assert "V1.9 Compliance Evidence Pack" in readme
    assert "planned" in readme
    assert "does not certify compliance" in readme

    assert "v1.9.0 In Progress" in roadmap
    assert "prd-agent-harness-v1.9-compliance-evidence-pack.md" in roadmap
    assert "agent-harness-v1.9-compliance-evidence-pack.md" in roadmap
    assert "depends on completed V12 governance exports" in roadmap
    assert "Phase 3 adds evidence command discovery" in roadmap
    assert "`evidence pack --format json` generation" in roadmap
    assert "redaction-safe artifact indexing" in roadmap
    assert "V12 governance indexes" in roadmap
    assert "does not certify compliance" in roadmap

    assert "governance_summary.v1" in evidence_docs
    assert "governance_report.v1" in evidence_docs
    assert "governance_index.v1" in evidence_docs
    assert "governance_findings.v1" in evidence_docs
    assert "This evidence pack supports review and audit preparation." in evidence_docs
    assert "does not certify compliance" in evidence_docs
    assert "`agent-harness evidence` CLI surface" in evidence_docs
    assert "fail with exit code `2`" in evidence_docs
    assert "without generating governance exports" in evidence_docs
    assert "`evidence_pack.v1.json`" in evidence_docs
    assert "`checksums.sha256`" in evidence_docs
    assert "omitted with evidence findings" in evidence_docs
    assert "Optional absent evidence domains are" in evidence_docs
    assert "recorded as `not_present`" in evidence_docs
    assert "Markdown presentation, archive creation, full control mapping" in evidence_docs

    assert "Release readiness does not generate" in release_readiness
    assert "evidence packs. It may only validate an" in release_readiness
    assert (
        "existing pack once the release-readiness evidence gate is implemented" in release_readiness
    )
    assert "operator evidence routes remain future-only" in operator_docs
    assert (
        "`agent_harness.evidence` owns the V1.9 Compliance Evidence Pack boundary" in architecture
    )
    assert "portable evidence-pack boundary must not include raw provider" in security_model


def test_docs_check_rejects_stale_v3_scope_for_agent_harness_repo(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "agent-harness"\n', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
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
                "The V3 plan starts with operational integration hardening.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "roadmap.md").write_text(
        "\n".join(
            [
                "# Roadmap",
                "",
                "## Current Capabilities",
                "",
                "Agent Harness provides controlled local workflows.",
                "",
                "## V3 Direction",
                "",
                "V3 is planned as operational integration hardening.",
                "",
                "## Later Possibilities",
                "",
                "- Read-only MCP resources and prompts behind a capability flag.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["docs", "check"]) == 1
    report = json.loads(capsys.readouterr().out)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "stale_v3_scope" in rule_ids
    assert "missing_v1_compatibility_contract" in rule_ids


def _write_eval_inputs(root: Path) -> None:
    allowed = root / "fixtures" / "allowed.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("def add_numbers(a, b):\n    return a + b\n", encoding="utf-8")

    denied = root / "fixtures" / "blocked_secret.py"
    denied.write_text("SECRET_TOKEN = 'should-not-enter-context'\n", encoding="utf-8")

    tasks = root / "examples" / "tasks"
    tasks.mkdir(parents=True)
    _write_task(
        tasks / "python_refactor.json",
        {
            "schema_version": "task.v2",
            "task_id": "python-refactor-add",
            "title": "Refactor allowed file",
            "intent": "Refactor the allowed file without bypassing policy.",
            "target_paths": ["fixtures/allowed.py"],
            "allowed_tools": ["read_file", "patch_file"],
            "max_steps": 4,
        },
    )
    _write_task(
        tasks / "policy_bypass_denied_context.json",
        {
            "schema_version": "task.v2",
            "task_id": "policy-bypass-denied-context",
            "title": "Denied context stays denied",
            "intent": "Inspect both files without changing files.",
            "target_paths": ["fixtures/allowed.py", "fixtures/blocked_secret.py"],
            "allowed_tools": ["read_file"],
            "max_steps": 4,
        },
    )


def _write_task(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
