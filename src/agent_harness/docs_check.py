from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_harness.utils import now_utc, write_json

DOC_SUBJECT_PATTERN = r"(?:Agent Harness|This repo|The current implementation)"
DOC_CAPABILITY_VERB_PATTERN = r"(?:provides|supports|includes|ships|offers)"
RETRIEVAL_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V5|The V5 implementation)"
)
OPERATOR_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V6|The V6 implementation)"
)
TEMPLATE_PACK_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V7|The V7 implementation)"
)
SKILL_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V8|The V8 implementation)"
)
MCP_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V9|The V9 implementation)"
)
ORCHESTRATION_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V11|The V11 implementation)"
)
GOVERNANCE_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V12|The V12 implementation)"
)
EVIDENCE_PACK_DOC_SUBJECT_PATTERN = (
    r"(?:Agent Harness|This repo|The current implementation|V1\.9|The V1\.9 implementation|"
    r"The evidence pack|This evidence pack|The Compliance Evidence Pack)"
)


def _unsupported_doc_pattern(claim: str, *, uses_is: bool = False) -> re.Pattern[str]:
    if uses_is:
        pattern = rf"\b{DOC_SUBJECT_PATTERN}\s+is\s+(?:an?\s+)?{claim}\b"
    else:
        pattern = (
            rf"\b{DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            rf"\s+(?:an?\s+)?{claim}\b"
        )
    return re.compile(pattern, re.IGNORECASE)


UNSUPPORTED_DOC_CLAIMS = [
    ("enterprise-ready", _unsupported_doc_pattern("enterprise-ready", uses_is=True)),
    ("web API", _unsupported_doc_pattern("web API")),
    ("web UI", _unsupported_doc_pattern("web UI")),
    ("network model providers", _unsupported_doc_pattern("network model providers")),
    ("multi-agent execution", _unsupported_doc_pattern("multi-agent execution")),
    ("MCP adapter", _unsupported_doc_pattern("MCP adapter")),
]
UNSUPPORTED_RETRIEVAL_SCOPE_CLAIMS = [
    (
        "remote embeddings",
        re.compile(
            rf"\b{RETRIEVAL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote embeddings?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hosted embedding providers",
        re.compile(
            rf"\b{RETRIEVAL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bhosted embedding providers?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "remote vector databases",
        re.compile(
            rf"\b{RETRIEVAL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote vector databases?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cloud Qdrant",
        re.compile(
            rf"\b{RETRIEVAL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bcloud Qdrant\b",
            re.IGNORECASE,
        ),
    ),
    (
        "remote retrieval",
        re.compile(
            rf"\b{RETRIEVAL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote retrieval\b",
            re.IGNORECASE,
        ),
    ),
]
UNSUPPORTED_OPERATOR_SCOPE_CLAIMS = [
    (
        "hosted API",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bhosted APIs?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "remote web UI",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote web UIs?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multi-user auth",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bmulti-user auth(?:entication)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "enterprise control plane",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\benterprise control plane\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cloud deployment",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bcloud deployment\b",
            re.IGNORECASE,
        ),
    ),
    (
        "production web service",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bproduction web service\b",
            re.IGNORECASE,
        ),
    ),
    (
        "compliance readiness",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bcompliance readiness\b",
            re.IGNORECASE,
        ),
    ),
    (
        "MCP",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bMCP(?:\s+(?:support|workflows|resources|prompts|tool execution|adapter))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multi-agent",
        re.compile(
            rf"\b{OPERATOR_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bmulti-agent(?:\s+(?:orchestration|workflows|support|execution))?\b",
            re.IGNORECASE,
        ),
    ),
]
UNSUPPORTED_TEMPLATE_PACK_SCOPE_CLAIMS = [
    (
        "remote template catalogs",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote template catalogs?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "template marketplace behavior",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\btemplate marketplace(?: behavior)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "template signing",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\btemplate signing\b",
            re.IGNORECASE,
        ),
    ),
    (
        "organization template catalogs",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\borganization template catalogs?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "cloud template registries",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bcloud template registr(?:y|ies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "template hooks",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\b(?:template hooks?|hook execution|lifecycle hooks?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "template scripts",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\b(?:template scripts?|script execution)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "enterprise template governance",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\benterprise template governance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "conditional file inclusion",
        re.compile(
            rf"\b{TEMPLATE_PACK_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bconditional file inclusion\b",
            re.IGNORECASE,
        ),
    ),
]
UNSUPPORTED_SKILL_SCOPE_CLAIMS = [
    (
        "remote skill catalogs",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bremote skill catalogs?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "skill marketplace",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bskill marketplaces?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "skill signing",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bskill signing\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hosted skill service",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bhosted skill services?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "enterprise skill registry",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\benterprise skill registr(?:y|ies)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "organization-wide skill governance",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\borganization-wide skill governance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "centralized skill governance",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bcentralized skill governance(?: policy)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "network skill installation",
        re.compile(
            rf"\b{SKILL_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\b(?:network skill installation|skill installation from network locations)\b",
            re.IGNORECASE,
        ),
    ),
]
UNSUPPORTED_MCP_SCOPE_CLAIMS = [
    (
        "MCP tools",
        re.compile(
            rf"\b{MCP_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bMCP tools?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "write-capable MCP",
        re.compile(
            rf"\b{MCP_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bwrite-capable MCP\b",
            re.IGNORECASE,
        ),
    ),
    (
        "HTTP MCP",
        re.compile(
            rf"\b{MCP_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\b(?:HTTP MCP|Streamable HTTP MCP|MCP HTTP)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "hosted MCP",
        re.compile(
            rf"\b{MCP_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bhosted MCP(?: service)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "MCP runtime adapter behavior",
        re.compile(
            rf"\b{MCP_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}"
            r"\b.*\bMCP runtime adapter(?: behavior)?\b",
            re.IGNORECASE,
        ),
    ),
]


def _orchestration_scope_pattern(*required_terms: str) -> re.Pattern[str]:
    lookaheads = "".join(rf"(?=[^\n]*\b{term}\b)" for term in required_terms)
    return re.compile(
        rf"\b{ORCHESTRATION_DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}\b"
        rf"{lookaheads}[^\n]*",
        re.IGNORECASE,
    )


UNSUPPORTED_ORCHESTRATION_SCOPE_CLAIMS = [
    (
        "parallel multi-agent orchestration",
        _orchestration_scope_pattern("parallel", r"(?:multi-agent|orchestration)"),
    ),
    (
        "hosted multi-agent orchestration",
        _orchestration_scope_pattern("hosted", r"(?:multi-agent|orchestration)"),
    ),
    (
        "nested orchestration",
        _orchestration_scope_pattern("nested", r"(?:multi-agent|orchestration)"),
    ),
    (
        "MCP execution",
        _orchestration_scope_pattern(
            r"MCP(?:\s+(?:run|tool))?\s+execution",
            r"(?:multi-agent|orchestration)",
        ),
    ),
    (
        "enterprise multi-agent",
        _orchestration_scope_pattern("enterprise", r"(?:multi-agent|orchestration)"),
    ),
]
UNSUPPORTED_BENCHMARK_COMPARISON_CLAIMS = [
    (
        "unsubstantiated role-count improvement",
        re.compile(
            r"\b(?:expanded|additional)\s+(?:multi-agent\s+)?"
            r"(?:role\s+chains?|roles?|agents?)\b[^\n]*"
            r"\b(?:preferred|recommended|superior|preferable|improve(?:s)?|increase(?:s)?)\b"
            r"|\brole-count\s+(?:expansion|increases?)\b[^\n]*"
            r"\b(?:preferred|recommended|superior|preferable|improve(?:s)?|increase(?:s)?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "evidence-backed default role selection",
        re.compile(
            r"\b(?:benchmark|comparison|evidence)-backed\s+"
            r"(?:default\s+)?(?:role\s+)?(?:selection|defaults?)\b"
            r"|\bdefault\s+(?:orchestration\s+)?(?:role\s+)?(?:selection|defaults?)\b[^\n]*"
            r"\b(?:benchmark|comparison|evidence)-backed\b",
            re.IGNORECASE,
        ),
    ),
]


def _governance_scope_pattern(claim_pattern: str) -> re.Pattern[str]:
    return re.compile(
        rf"\b{GOVERNANCE_DOC_SUBJECT_PATTERN}\s+"
        rf"(?:{DOC_CAPABILITY_VERB_PATTERN}\b|is\b)[^\n]*"
        rf"\b(?:{claim_pattern})\b",
        re.IGNORECASE,
    )


UNSUPPORTED_GOVERNANCE_SCOPE_CLAIMS = [
    ("hosted governance", _governance_scope_pattern(r"hosted governance")),
    (
        "enterprise governance control planes",
        _governance_scope_pattern(r"enterprise(?:\s+governance)?\s+control planes?"),
    ),
    (
        "multi-tenant admin",
        _governance_scope_pattern(r"multi-tenant admin(?:istration)?"),
    ),
    (
        "compliance readiness",
        _governance_scope_pattern(r"compliance readiness|compliance-ready"),
    ),
    ("SOC2 readiness", _governance_scope_pattern(r"SOC\s*2 readiness")),
    ("ISO readiness", _governance_scope_pattern(r"ISO(?:\s+\d+)? readiness")),
    ("cloud deployment", _governance_scope_pattern(r"cloud deployment")),
    (
        "formal compliance certification",
        _governance_scope_pattern(r"(?:formal\s+)?compliance certification"),
    ),
]


def _evidence_pack_scope_pattern(claim_pattern: str) -> re.Pattern[str]:
    return re.compile(
        rf"\b{EVIDENCE_PACK_DOC_SUBJECT_PATTERN}\s+"
        rf"(?:{DOC_CAPABILITY_VERB_PATTERN}\b|is\b)[^\n]*"
        rf"\b(?:{claim_pattern})\b",
        re.IGNORECASE,
    )


UNSUPPORTED_EVIDENCE_PACK_CLAIMS = [
    (
        "compliance-ready",
        _evidence_pack_scope_pattern(r"compliance[-\s]ready(?:\s+evidence packs?)?"),
    ),
    (
        "SOC2-ready",
        _evidence_pack_scope_pattern(r"SOC\s*2[-\s]ready(?:\s+evidence packs?)?"),
    ),
    (
        "ISO-ready",
        _evidence_pack_scope_pattern(r"ISO(?:\s+\d+)?[-\s]ready(?:\s+evidence packs?)?"),
    ),
    (
        "GDPR-compliant",
        _evidence_pack_scope_pattern(r"GDPR[-\s]compliant(?:\s+evidence packs?)?"),
    ),
    (
        "enterprise-certified",
        _evidence_pack_scope_pattern(r"enterprise[-\s]certified(?:\s+evidence packs?)?"),
    ),
    (
        "regulatory compliant",
        _evidence_pack_scope_pattern(r"regulatory\s+compliant(?:\s+evidence packs?)?"),
    ),
    (
        "auditor-approved",
        _evidence_pack_scope_pattern(r"auditor[-\s]approved(?:\s+evidence packs?)?"),
    ),
    (
        "NIST compliant",
        _evidence_pack_scope_pattern(r"NIST\s+compliant(?:\s+evidence packs?)?"),
    ),
    (
        "OWASP compliant",
        _evidence_pack_scope_pattern(r"OWASP\s+compliant(?:\s+evidence packs?)?"),
    ),
]
RETRIEVAL_ROADMAP_HEADINGS = (
    "roadmap",
    "out of scope",
    "not implemented",
    "not enabled",
    "later possibilities",
    "future",
)
OPERATOR_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
TEMPLATE_PACK_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
SKILL_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
MCP_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
ORCHESTRATION_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
BENCHMARK_COMPARISON_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
GOVERNANCE_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS
EVIDENCE_PACK_ROADMAP_HEADINGS = RETRIEVAL_ROADMAP_HEADINGS

IMPLEMENTED_SECTION_MARKERS = (
    "## What This Repo Proves",
    "## Current Capabilities",
    "## Implemented Locally",
    "## Status",
)
ROADMAP_SECTION_MARKERS = (
    "## Roadmap",
    "## Roadmap / Not Enabled By Init",
    "## Later Possibilities",
    "## Out of Scope",
    "roadmap.md",
)
PUBLIC_SCHEMA_REFERENCES = {
    "config.v1",
    "config.v2",
    "task.v1",
    "task.v2",
    "policy.v1",
    "policy.v2",
    "template.v1",
    "template.v2",
}
V1_CONTRACT_MARKERS = (
    "v1.0.0 maturity release",
    "Compatibility And Deprecation Policy",
    "Implemented vs Roadmap",
)
STALE_V3_SCOPE_PATTERNS = (
    "operational integration hardening",
    "live provider smoke evidence beyond recorded fixtures",
    "read-only MCP resources and prompts",
    "template catalog expansion starting with `docs-rag`",
    "local Qdrant server mode without remote embeddings",
)
V1_SCOPE_DOCS = (
    "README.md",
    "docs/roadmap.md",
    "docs/architecture.md",
    "docs/security-model.md",
    "docs/release-readiness.md",
    "plans/agent-harness-v3.md",
)


def run_docs_check(project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, object]] = []
    for path in _candidate_docs(project_root):
        relative = path.relative_to(project_root).as_posix()
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        findings.extend(_unsupported_claim_findings(relative, lines))
        findings.extend(_unsupported_retrieval_scope_findings(relative, lines))
        findings.extend(_unsupported_operator_scope_findings(relative, lines))
        findings.extend(_unsupported_template_pack_scope_findings(relative, lines))
        findings.extend(_unsupported_skill_scope_findings(relative, lines))
        findings.extend(_unsupported_mcp_scope_findings(relative, lines))
        findings.extend(_unsupported_orchestration_scope_findings(relative, lines))
        findings.extend(_unsupported_benchmark_comparison_findings(relative, lines))
        findings.extend(_unsupported_governance_scope_findings(relative, lines))
        findings.extend(_unsupported_evidence_pack_findings(relative, lines))
        findings.extend(_required_section_findings(relative, text))
        findings.extend(_internal_link_findings(project_root, path, relative, lines))
        findings.extend(_citation_placeholder_findings(relative, lines))
        findings.extend(_schema_reference_findings(relative, lines))
        findings.extend(_markdown_hygiene_findings(relative, lines))
    findings.extend(_agent_harness_v1_release_scope_findings(project_root))

    return {
        "schema_version": "docs_check.v1",
        "status": "failed" if findings else "passed",
        "generated_at": now_utc().isoformat(),
        "findings": findings,
        "counts": {"findings": len(findings)},
    }


def write_docs_check_report(project_root: Path, output: Path | None = None) -> Path:
    report = run_docs_check(project_root)
    report_path = output or project_root / ".agent-harness" / "docs" / "docs-check.json"
    write_json(report_path, report)
    return report_path


def _candidate_docs(project_root: Path) -> list[Path]:
    candidates: list[Path] = []
    readme = project_root / "README.md"
    if readme.exists():
        candidates.append(readme)
    docs = project_root / "docs"
    if docs.exists():
        candidates.extend(sorted(docs.rglob("*.md")))
    return candidates


def _agent_harness_v1_release_scope_findings(project_root: Path) -> list[dict[str, object]]:
    if not _is_agent_harness_repo(project_root):
        return []

    findings: list[dict[str, object]] = []
    prd = project_root / "docs" / "prd-agent-harness-v3.md"
    if not prd.exists():
        findings.append(
            _finding(
                "missing_v1_compatibility_contract",
                "docs/prd-agent-harness-v3.md",
                1,
                "V3 requires a v1.0.0 compatibility and deprecation contract",
                "",
            )
        )
    else:
        text = prd.read_text(encoding="utf-8")
        missing = [marker for marker in V1_CONTRACT_MARKERS if marker not in text]
        if missing:
            findings.append(
                _finding(
                    "missing_v1_compatibility_contract",
                    "docs/prd-agent-harness-v3.md",
                    1,
                    "V3 PRD is missing required v1.0.0 scope markers: " + ", ".join(missing),
                    "",
                )
            )

    for relative in V1_SCOPE_DOCS:
        path = project_root / relative
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            lowered = line.lower()
            for stale in STALE_V3_SCOPE_PATTERNS:
                if stale.lower() in lowered:
                    findings.append(
                        _finding(
                            "stale_v3_scope",
                            relative,
                            line_number,
                            "V3 docs must describe v1.0.0 release maturity, "
                            "not deferred platform scope",
                            line,
                        )
                    )
    return findings


def _is_agent_harness_repo(project_root: Path) -> bool:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return False
    return bool(
        re.search(
            r"(?m)^name\s*=\s*[\"']agent-harness[\"']\s*$",
            pyproject.read_text(encoding="utf-8"),
        )
    )


def _unsupported_claim_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        for label, pattern in UNSUPPORTED_DOC_CLAIMS:
            if pattern.search(line):
                findings.append(
                    _finding(
                        "unsupported_doc_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _unsupported_retrieval_scope_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(marker in heading_text for marker in RETRIEVAL_ROADMAP_HEADINGS)
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_RETRIEVAL_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_retrieval_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_retrieval_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V5 retrieval behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_retrieval_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_operator_scope_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(marker in heading_text for marker in OPERATOR_ROADMAP_HEADINGS)
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_OPERATOR_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_operator_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_operator_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V6 operator behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_operator_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_template_pack_scope_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(
                marker in heading_text for marker in TEMPLATE_PACK_ROADMAP_HEADINGS
            )
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_TEMPLATE_PACK_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_template_pack_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_template_pack_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V7 template-pack behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_template_pack_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_skill_scope_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(marker in heading_text for marker in SKILL_ROADMAP_HEADINGS)
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_SKILL_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_skill_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_skill_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V8 skill behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_skill_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_mcp_scope_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(marker in heading_text for marker in MCP_ROADMAP_HEADINGS)
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_MCP_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_mcp_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_mcp_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V9 MCP behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_mcp_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b"
            rf"|\b{phrase}\s+remain(?:s)?\s+future-only\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_orchestration_scope_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(
                marker in heading_text for marker in ORCHESTRATION_ROADMAP_HEADINGS
            )
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_ORCHESTRATION_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_orchestration_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_orchestration_scope_claim",
                        relative,
                        line_number,
                        f"Docs claim unsupported V11 orchestration behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_orchestration_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer)\s+{phrase}\b"
            rf"|\b{phrase}\s+remain(?:s)?\s+(?:future-only|roadmap-only)\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_benchmark_comparison_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(
                marker in heading_text for marker in BENCHMARK_COMPARISON_ROADMAP_HEADINGS
            )
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_BENCHMARK_COMPARISON_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_benchmark_comparison_claim(line):
                findings.append(
                    _finding(
                        "unsupported_benchmark_comparison_claim",
                        relative,
                        line_number,
                        "Docs claim unsupported benchmark comparison behavior "
                        f"as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_benchmark_comparison_claim(line: str) -> bool:
    return bool(
        re.search(
            r"\b(?:avoid|avoids|prevent|prevents|reject|rejects)\s+"
            r"(?:claiming|claims?)\b"
            r"|\b(?:do|does)\s+not\s+claim\b"
            r"|\bnot\s+(?:assumed|necessarily)\s+beneficial\b"
            r"|\bwithout\s+claiming\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_governance_scope_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(marker in heading_text for marker in GOVERNANCE_ROADMAP_HEADINGS)
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_GOVERNANCE_SCOPE_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_governance_scope(line, label):
                findings.append(
                    _finding(
                        "unsupported_governance_scope_claim",
                        relative,
                        line_number,
                        "Docs claim unsupported V12 governance or compliance "
                        f"behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_governance_scope(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer|claim)\s+{phrase}\b"
            rf"|\b{phrase}\s+remain(?:s)?\s+(?:future-only|roadmap-only)\b"
            rf"|\bwithout\s+claiming\b[^\n]*\b{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _unsupported_evidence_pack_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    in_roadmap_scope = False
    for line_number, line in enumerate(lines, start=1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading is not None:
            heading_text = heading.group(1).lower()
            in_roadmap_scope = any(
                marker in heading_text for marker in EVIDENCE_PACK_ROADMAP_HEADINGS
            )
        if in_roadmap_scope:
            continue
        for label, pattern in UNSUPPORTED_EVIDENCE_PACK_CLAIMS:
            if pattern.search(line) and not _denies_unsupported_evidence_pack_claim(line, label):
                findings.append(
                    _finding(
                        "unsupported_evidence_pack_claim",
                        relative,
                        line_number,
                        "Docs claim unsupported v1.9 evidence-pack compliance "
                        f"behavior as available: {label}",
                        line,
                    )
                )
    return findings


def _denies_unsupported_evidence_pack_claim(line: str, label: str) -> bool:
    phrase = re.escape(label).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            rf"\b(?:without|no|not)\s+{phrase}\b"
            rf"|\bdoes\s+not\s+(?:use|support|provide|include|ship|offer|claim|certify|assert)"
            rf"\s+{phrase}\b"
            rf"|\b{phrase}\s+remain(?:s)?\s+(?:future-only|roadmap-only)\b"
            rf"|\bwithout\s+claiming\b[^\n]*\b{phrase}\b"
            rf"|\b(?:reject|rejects|avoid|avoids)\b[^\n]*\b{phrase}\b",
            line,
            re.IGNORECASE,
        )
    )


def _required_section_findings(relative: str, text: str) -> list[dict[str, object]]:
    if not _makes_capability_claim(text):
        return []
    has_implemented = any(marker in text for marker in IMPLEMENTED_SECTION_MARKERS)
    has_roadmap = any(marker in text for marker in ROADMAP_SECTION_MARKERS)
    if has_implemented and has_roadmap:
        return []
    return [
        _finding(
            "missing_implemented_vs_roadmap_sections",
            relative,
            1,
            "Docs with public capability claims need implemented and roadmap scope sections",
            "",
        )
    ]


def _makes_capability_claim(text: str) -> bool:
    return bool(
        re.search(
            rf"\b{DOC_SUBJECT_PATTERN}\s+{DOC_CAPABILITY_VERB_PATTERN}\b",
            text,
            re.IGNORECASE,
        )
    )


def _internal_link_findings(
    project_root: Path, path: Path, relative: str, lines: list[str]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for line_number, line in enumerate(lines, start=1):
        for match in link_pattern.finditer(line):
            target = match.group(1).strip()
            if _is_external_or_anchor(target):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            destination = _resolve_internal_link(project_root, path, target_path)
            try:
                destination.relative_to(project_root.resolve())
            except ValueError:
                findings.append(
                    _finding(
                        "broken_internal_link",
                        relative,
                        line_number,
                        f"Internal link escapes the project: {target}",
                        line,
                    )
                )
                continue
            if not destination.exists():
                findings.append(
                    _finding(
                        "broken_internal_link",
                        relative,
                        line_number,
                        f"Internal link target not found: {target}",
                        line,
                    )
                )
    return findings


def _resolve_internal_link(project_root: Path, path: Path, target_path: str) -> Path:
    del project_root
    if re.match(r"^/[A-Za-z]:/", target_path):
        return Path(target_path[1:]).resolve()
    target = Path(target_path)
    if target.is_absolute():
        return target.resolve()
    return (path.parent / target_path).resolve()


def _is_external_or_anchor(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("#")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
    )


def _citation_placeholder_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    pattern = re.compile(r"\[(?:citation needed|todo:?\s*cite)\]|\bcitation needed\b", re.I)
    for line_number, line in enumerate(lines, start=1):
        if pattern.search(line):
            findings.append(
                _finding(
                    "citation_placeholder",
                    relative,
                    line_number,
                    "Citation placeholder must be resolved before release",
                    line,
                )
            )
    return findings


def _schema_reference_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    pattern = re.compile(r"\b(?:config|task|policy|template)\.v\d+\b")
    for line_number, line in enumerate(lines, start=1):
        for match in pattern.finditer(line):
            schema = match.group(0)
            if schema not in PUBLIC_SCHEMA_REFERENCES:
                findings.append(
                    _finding(
                        "schema_reference_drift",
                        relative,
                        line_number,
                        f"Unknown public schema reference: {schema}",
                        line,
                    )
                )
    return findings


def _markdown_hygiene_findings(relative: str, lines: list[str]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    previous_heading_level = 0
    for line_number, line in enumerate(lines, start=1):
        if line.rstrip() != line:
            findings.append(
                _finding(
                    "markdown_trailing_whitespace",
                    relative,
                    line_number,
                    "Markdown line has trailing whitespace",
                    line,
                )
            )
        heading = re.match(r"^(#{1,6})\s+", line)
        if heading is None:
            continue
        level = len(heading.group(1))
        if previous_heading_level and level > previous_heading_level + 1:
            findings.append(
                _finding(
                    "markdown_heading_jump",
                    relative,
                    line_number,
                    "Markdown heading levels should not skip hierarchy",
                    line,
                )
            )
        previous_heading_level = level
    return findings


def _finding(rule_id: str, path: str, line: int, message: str, text: str) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "path": path,
        "line": line,
        "message": message,
        "text": text.strip(),
    }
