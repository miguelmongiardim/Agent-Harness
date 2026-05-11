from __future__ import annotations

from agent_harness.review.schema import (
    ReviewDurationClass,
    ReviewProfile,
    ReviewProfileCatalog,
    ReviewProfileCommand,
)
from agent_harness.utils import now_utc


def build_profile_catalog() -> ReviewProfileCatalog:
    quick = _quick_profile()
    standard = _standard_profile(quick.commands)
    release = _release_profile(standard.commands)
    profiles = [quick, standard, release]
    _validate_builtin_profiles(profiles)
    return ReviewProfileCatalog(
        generated_at=now_utc().isoformat(),
        profiles=profiles,
    )


def get_profile(profile_id: str) -> ReviewProfile:
    for profile in build_profile_catalog().profiles:
        if profile.profile_id == profile_id:
            return profile
    raise ValueError(f"unknown review profile: {profile_id}")


def render_profile_catalog_text(catalog: ReviewProfileCatalog) -> str:
    lines: list[str] = []
    for profile in catalog.profiles:
        lines.append(f"{profile.profile_id}: {profile.title}")
        lines.append(f"  duration: {profile.expected_duration_class}")
        lines.append(f"  {profile.description}")
        for command in profile.commands:
            required = "required" if command.required else "optional"
            lines.append(f"  - {command.command} ({required}, {command.expected_duration_class})")
        lines.append("")
    return "\n".join(lines).rstrip()


def _quick_profile() -> ReviewProfile:
    return ReviewProfile(
        profile_id="quick",
        title="Quick Review",
        description="Fast local checks for routine contribution review.",
        expected_duration_class="fast",
        commands=[
            _command(
                "doctor",
                "agent-harness doctor",
                ["agent-harness", "doctor"],
                required=True,
                duration="fast",
                mutates=False,
                evidence=["Doctor output shows local configuration health."],
            ),
            _command(
                "docs_check",
                "agent-harness docs check",
                ["agent-harness", "docs", "check"],
                required=True,
                duration="fast",
                mutates=True,
                evidence=["Docs check report is available under .agent-harness/docs/."],
            ),
            _command(
                "pytest_quick",
                "python -m pytest -q",
                ["python", "-m", "pytest", "-q"],
                required=True,
                duration="fast",
                mutates=False,
                evidence=["Pytest exit code and output summarize the quick test suite."],
            ),
        ],
    )


def _standard_profile(quick_commands: list[ReviewProfileCommand]) -> ReviewProfile:
    return ReviewProfile(
        profile_id="standard",
        title="Standard Review",
        description="Broader local checks for public behavior, docs, and shared boundaries.",
        expected_duration_class="moderate",
        commands=[
            *quick_commands,
            _command(
                "ruff",
                "python -m ruff check src tests",
                ["python", "-m", "ruff", "check", "src", "tests"],
                required=True,
                duration="moderate",
                mutates=False,
                evidence=["Ruff reports lint status for source and tests."],
            ),
            _command(
                "mypy",
                "python -m mypy",
                ["python", "-m", "mypy"],
                required=True,
                duration="moderate",
                mutates=False,
                evidence=["Mypy reports public typing boundary status."],
            ),
            _command(
                "compileall",
                "python -m compileall -q src tests",
                ["python", "-m", "compileall", "-q", "src", "tests"],
                required=True,
                duration="moderate",
                mutates=False,
                evidence=["Compileall confirms importable Python files."],
            ),
            _command(
                "eval",
                "agent-harness eval",
                ["agent-harness", "eval"],
                required=True,
                duration="moderate",
                mutates=True,
                evidence=["Eval report is available under .agent-harness/evals/."],
            ),
            _command(
                "template_validate_all",
                "agent-harness template validate --all",
                ["agent-harness", "template", "validate", "--all"],
                required=True,
                duration="moderate",
                mutates=True,
                evidence=["Template validation evidence is recorded for bundled templates."],
            ),
        ],
    )


def _release_profile(standard_commands: list[ReviewProfileCommand]) -> ReviewProfile:
    return ReviewProfile(
        profile_id="release",
        title="Release Review",
        description="Release-oriented local checks that prepare final readiness evidence.",
        expected_duration_class="release",
        commands=[
            *standard_commands,
            _command(
                "pre_commit",
                "python -m pre_commit run --all-files",
                ["python", "-m", "pre_commit", "run", "--all-files"],
                required=True,
                duration="slow",
                mutates=False,
                evidence=["Pre-commit output summarizes configured repository checks."],
            ),
            _command(
                "pytest_slow",
                "python -m pytest -m slow",
                ["python", "-m", "pytest", "-m", "slow"],
                required=True,
                duration="slow",
                mutates=True,
                evidence=["Slow pytest output covers release-gated integration paths."],
            ),
            _command(
                "package_check",
                "agent-harness release package-check",
                ["agent-harness", "release", "package-check"],
                required=True,
                duration="slow",
                mutates=True,
                evidence=["Package check evidence is written under .agent-harness/release/."],
            ),
            _command(
                "demo_provider_audit",
                "agent-harness demo provider-audit",
                ["agent-harness", "demo", "provider-audit"],
                required=True,
                duration="slow",
                mutates=True,
                evidence=["Provider audit demo evidence is written for release review."],
            ),
            _command(
                "demo_python_refactor",
                "agent-harness run examples/tasks/python_refactor.json --dry-run",
                [
                    "agent-harness",
                    "run",
                    "examples/tasks/python_refactor.json",
                    "--dry-run",
                ],
                required=True,
                duration="slow",
                mutates=True,
                evidence=["Python refactor dry-run evidence is written for release review."],
            ),
            _command(
                "governance_export",
                "agent-harness governance export --output .agent-harness/governance/",
                [
                    "agent-harness",
                    "governance",
                    "export",
                    "--output",
                    ".agent-harness/governance/",
                ],
                required=True,
                duration="slow",
                mutates=True,
                evidence=[
                    "Governance export artifacts are available under .agent-harness/governance/."
                ],
            ),
            _command(
                "evidence_pack",
                "agent-harness evidence pack",
                ["agent-harness", "evidence", "pack"],
                required=True,
                duration="slow",
                mutates=True,
                evidence=["Evidence pack artifacts are available under .agent-harness/evidence/."],
            ),
            _command(
                "release_readiness",
                "agent-harness release readiness",
                ["agent-harness", "release", "readiness"],
                required=True,
                duration="release",
                mutates=True,
                evidence=["Release readiness report links final local release evidence."],
            ),
        ],
    )


def _command(
    command_id: str,
    command: str,
    argv: list[str],
    *,
    required: bool,
    duration: ReviewDurationClass,
    mutates: bool,
    evidence: list[str],
) -> ReviewProfileCommand:
    return ReviewProfileCommand(
        command_id=command_id,
        command=command,
        argv=argv,
        required=required,
        expected_duration_class=duration,
        mutates_artifacts=mutates,
        evidence_expectations=evidence,
    )


def _validate_builtin_profiles(profiles: list[ReviewProfile]) -> None:
    profile_ids = [profile.profile_id for profile in profiles]
    if profile_ids != ["quick", "standard", "release"]:
        raise ValueError("review profiles must be quick, standard, and release in order")
    if len(set(profile_ids)) != len(profile_ids):
        raise ValueError("review profile ids must be unique")
    for profile in profiles:
        command_ids = [command.command_id for command in profile.commands]
        if len(set(command_ids)) != len(command_ids):
            raise ValueError(f"review profile {profile.profile_id} has duplicate commands")
