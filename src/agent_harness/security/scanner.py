from __future__ import annotations

import re
from pathlib import Path

from agent_harness.policy import PolicyEngine
from agent_harness.schemas import (
    SecurityFinding,
    SecurityFindingsReport,
    SecurityGateDecision,
    SecuritySeverity,
    TaskSpec,
)
from agent_harness.utils import stable_id

SCANNER_ID = "first_party_static"

_SEVERITY_RANK: dict[SecuritySeverity, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}
_CREDENTIAL_LITERAL = re.compile(
    r"(?i)\b(api[_-]?key|secret[_-]?token|access[_-]?token|private[_-]?key)\b"
    r"\s*=\s*(['\"])[^'\"]+\2"
)
_PASSWORD_LITERAL = re.compile(r"(?i)\bpassword\b\s*=\s*(['\"])[^'\"]+\1")
_DANGEROUS_SHELL = re.compile(
    r"(?i)(subprocess\.(run|call|popen)\s*\(.*\bshell\s*=\s*True\b|os\.system\s*\()"
)
_SECURITY_TODO = re.compile(r"(?i)(\bTODO\b.*\bsecurity\b|\bsecurity\b.*\bTODO\b)")


def scan_task_security(
    project_root: Path,
    run_id: str,
    task: TaskSpec,
    policy: PolicyEngine,
) -> SecurityFindingsReport:
    del project_root
    findings: list[SecurityFinding] = []
    for target_path in task.target_paths:
        path_decision = policy.evaluate_path(target_path, "read", "security_scan")
        if not path_decision.allowed:
            findings.append(
                _finding(
                    run_id=run_id,
                    rule_id="security-scan-path-denied",
                    severity="info",
                    path=target_path,
                    line=None,
                    message="security scan target was skipped by read policy",
                    evidence=path_decision.reason,
                )
            )
            continue

        path = policy.resolve_relative(target_path)
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        findings.extend(_scan_text(run_id, target_path, text))

    threshold = policy.profile.security_fail_threshold
    blocking = [
        finding.finding_id
        for finding in findings
        if _SEVERITY_RANK[finding.severity] >= _SEVERITY_RANK[threshold]
    ]
    return SecurityFindingsReport(
        run_id=run_id,
        task_id=task.task_id,
        findings=findings,
        gate=SecurityGateDecision(
            status="failed" if blocking else "passed",
            fail_threshold=threshold,
            blocking_finding_ids=blocking,
        ),
    )


def _scan_text(run_id: str, path: str, text: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        credential_match = _CREDENTIAL_LITERAL.search(stripped)
        if credential_match:
            findings.append(
                _finding(
                    run_id=run_id,
                    rule_id="credential-literal",
                    severity="critical",
                    path=path,
                    line=line_number,
                    message="credential-like literal found",
                    evidence=f"{credential_match.group(1)} = <redacted>",
                )
            )
        if _PASSWORD_LITERAL.search(stripped):
            findings.append(
                _finding(
                    run_id=run_id,
                    rule_id="password-literal-review",
                    severity="medium",
                    path=path,
                    line=line_number,
                    message="password-like literal should be reviewed before provider use",
                    evidence="password = <redacted>",
                )
            )
        if _DANGEROUS_SHELL.search(stripped):
            findings.append(
                _finding(
                    run_id=run_id,
                    rule_id="python-dangerous-shell",
                    severity="high",
                    path=path,
                    line=line_number,
                    message="shell execution is enabled in a Python subprocess call",
                    evidence=stripped,
                )
            )
        if _SECURITY_TODO.search(stripped):
            findings.append(
                _finding(
                    run_id=run_id,
                    rule_id="security-review-todo",
                    severity="medium",
                    path=path,
                    line=line_number,
                    message="security review marker found",
                    evidence=stripped,
                )
            )
    return findings


def _finding(
    *,
    run_id: str,
    rule_id: str,
    severity: SecuritySeverity,
    path: str,
    line: int | None,
    message: str,
    evidence: str | None,
) -> SecurityFinding:
    return SecurityFinding(
        finding_id=stable_id("security_finding", run_id, rule_id, path, line, message, evidence),
        rule_id=rule_id,
        severity=severity,
        scanner=SCANNER_ID,
        path=path,
        line=line,
        message=message,
        evidence=evidence,
    )
