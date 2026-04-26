from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_harness.utils import now_utc, write_json

DOC_SUBJECT_PATTERN = r"(?:Agent Harness|This repo|The current implementation)"
DOC_CAPABILITY_VERB_PATTERN = r"(?:provides|supports|includes|ships|offers)"


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
                    "V3 PRD is missing required v1.0.0 scope markers: "
                    + ", ".join(missing),
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


def _unsupported_claim_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
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


def _citation_placeholder_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
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


def _schema_reference_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
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


def _markdown_hygiene_findings(
    relative: str, lines: list[str]
) -> list[dict[str, object]]:
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


def _finding(
    rule_id: str, path: str, line: int, message: str, text: str
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "path": path,
        "line": line,
        "message": message,
        "text": text.strip(),
    }
