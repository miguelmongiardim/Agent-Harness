from __future__ import annotations

import shutil
from pathlib import Path

from agent_harness.review.profiles import get_profile
from agent_harness.review.schema import (
    ReviewAvailabilityStatus,
    ReviewCommandStatus,
    ReviewMissingEvidence,
    ReviewNextAction,
    ReviewProfileCommand,
    ReviewStatus,
)
from agent_harness.utils import now_utc


def build_review_status(project_root: Path, profile_id: str) -> ReviewStatus:
    profile = get_profile(profile_id)
    command_statuses = [_command_status(project_root, command) for command in profile.commands]
    missing = [
        ReviewMissingEvidence(
            command_id=status.command_id,
            command=status.command,
            required=status.required,
            action=_missing_action(status.command),
        )
        for status in command_statuses
        if status.evidence_status == "missing"
    ]
    next_actions = [
        ReviewNextAction(
            command_id=item.command_id,
            command=item.command,
            action=item.action,
        )
        for item in missing
    ]
    return ReviewStatus(
        generated_at=now_utc().isoformat(),
        profile_id=profile.profile_id,
        expected_duration_class=profile.expected_duration_class,
        commands=command_statuses,
        missing_evidence=missing,
        next_actions=next_actions,
    )


def render_review_status_text(status: ReviewStatus) -> str:
    lines = [f"{status.profile_id}: {status.expected_duration_class}"]
    for command in status.commands:
        lines.append(
            f"- {command.command}: {command.evidence_status} evidence, "
            f"{command.availability_status} command"
        )
    if status.next_actions:
        lines.append("")
        lines.append("Next actions:")
        for action in status.next_actions:
            lines.append(f"- {action.command}: {action.action}")
    return "\n".join(lines)


def _command_status(project_root: Path, command: ReviewProfileCommand) -> ReviewCommandStatus:
    evidence_refs = _evidence_refs(project_root, command.command_id)
    return ReviewCommandStatus(
        command_id=command.command_id,
        command=command.command,
        required=command.required,
        availability_status=_availability_status(command.argv),
        evidence_status="present" if evidence_refs else "missing",
        evidence_refs=evidence_refs,
        next_actions=[] if evidence_refs else [_missing_action(command.command)],
    )


def _availability_status(argv: list[str]) -> ReviewAvailabilityStatus:
    if not argv:
        return "missing"
    if argv[0] == "agent-harness":
        return "available"
    return "available" if shutil.which(argv[0]) else "missing"


def _evidence_refs(project_root: Path, command_id: str) -> list[str]:
    single_artifacts = {
        "docs_check": project_root / ".agent-harness" / "docs" / "docs-check.json",
        "package_check": project_root / ".agent-harness" / "release" / "package-check.json",
        "template_validate_all": (
            project_root / ".agent-harness" / "release" / "evidence" / "template-validation.json"
        ),
    }
    if command_id in single_artifacts:
        path = single_artifacts[command_id]
        return [_project_relative(project_root, path)] if path.exists() else []
    if command_id == "eval":
        return _latest_matches(project_root, ".agent-harness/evals/eval-*.json")
    if command_id == "governance_export":
        return _existing_refs(
            project_root,
            [
                ".agent-harness/governance/governance_summary.v1.json",
                ".agent-harness/governance/governance_report.v1.json",
                ".agent-harness/governance/governance_index.v1.json",
                ".agent-harness/governance/governance_findings.v1.json",
            ],
        )
    if command_id == "evidence_pack":
        return _existing_refs(
            project_root,
            [
                ".agent-harness/evidence/evidence_pack.v1.json",
                ".agent-harness/evidence/evidence_manifest.v1.json",
                ".agent-harness/evidence/evidence_index.v1.json",
                ".agent-harness/evidence/evidence_findings.v1.json",
                ".agent-harness/evidence/control_mapping.v1.json",
            ],
        )
    if command_id == "release_readiness":
        return _latest_matches(project_root, ".agent-harness/release/v*-readiness.json")
    return []


def _latest_matches(project_root: Path, pattern: str) -> list[str]:
    paths = sorted(project_root.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        return []
    return [_project_relative(project_root, paths[0])]


def _existing_refs(project_root: Path, relatives: list[str]) -> list[str]:
    return [relative for relative in relatives if (project_root / relative).exists()]


def _missing_action(command: str) -> str:
    return f"Run `{command}` or `agent-harness review run` to refresh review evidence."


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
