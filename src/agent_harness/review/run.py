from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from agent_harness.review.profiles import get_profile
from agent_harness.review.schema import (
    ReviewCommandRunStatus,
    ReviewNextAction,
    ReviewProfileCommand,
    ReviewRun,
    ReviewRunCommandResult,
    ReviewRunStatus,
)
from agent_harness.review.status import _evidence_refs, _project_relative
from agent_harness.utils import now_utc, write_json

DEFAULT_COMMAND_TIMEOUT_SECONDS = 1800
SUMMARY_LIMIT = 1200


@dataclass(frozen=True)
class CommandExecutionResult:
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float


def build_review_run(
    project_root: Path,
    profile_id: str,
    *,
    ci_run_id: str | None = None,
) -> tuple[ReviewRun, int]:
    profile = get_profile(profile_id)
    generated_at = now_utc()
    artifact_path = (
        project_root
        / ".agent-harness"
        / "review"
        / f"review-run-{generated_at.strftime('%Y%m%dT%H%M%SZ')}-{profile.profile_id}.json"
    )
    results: list[ReviewRunCommandResult] = []
    next_actions: list[ReviewNextAction] = []
    for command in profile.commands:
        result = _execute_profile_command(project_root, command, ci_run_id=ci_run_id)
        results.append(result)
        if result.required and result.status == "failed":
            next_actions.append(
                ReviewNextAction(
                    command_id=result.command_id,
                    command=result.command,
                    action=f"Resolve `{result.command}` before treating the review as passing.",
                )
            )
    status: ReviewRunStatus = (
        "failed"
        if any(result.required and result.status == "failed" for result in results)
        else "passed"
    )
    run = ReviewRun(
        generated_at=generated_at.isoformat(),
        profile_id=profile.profile_id,
        status=status,
        commands=results,
        artifact=_project_relative(project_root, artifact_path),
        next_actions=next_actions,
    )
    write_json(artifact_path, run.model_dump(mode="json"))
    return run, 0 if status == "passed" else 1


def _execute_profile_command(
    project_root: Path,
    command: ReviewProfileCommand,
    *,
    ci_run_id: str | None,
) -> ReviewRunCommandResult:
    argv, command_text = _runtime_command(command, ci_run_id=ci_run_id)
    result = _run_command(
        argv,
        cwd=project_root,
        timeout_seconds=DEFAULT_COMMAND_TIMEOUT_SECONDS,
    )
    status: ReviewCommandRunStatus = "passed" if result.return_code == 0 else "failed"
    return ReviewRunCommandResult(
        command_id=command.command_id,
        command=command_text,
        argv=argv,
        required=command.required,
        status=status,
        return_code=result.return_code,
        duration_seconds=round(result.duration_seconds, 3),
        stdout_summary=_safe_output_summary(result.stdout),
        stderr_summary=_safe_output_summary(result.stderr),
        evidence_refs=_evidence_refs(project_root, command.command_id),
        skipped_reason=None,
        next_actions=[] if status == "passed" else [f"Inspect and rerun `{command_text}`."],
    )


def _runtime_command(
    command: ReviewProfileCommand,
    *,
    ci_run_id: str | None,
) -> tuple[list[str], str]:
    argv = list(command.argv)
    command_text = command.command
    if command.command_id == "release_readiness" and ci_run_id:
        argv.extend(["--ci-run-id", ci_run_id])
        command_text = f"{command.command} --ci-run-id {ci_run_id}"
    return argv, command_text


def _run_command(
    argv: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> CommandExecutionResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            _subprocess_argv(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandExecutionResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.perf_counter() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandExecutionResult(
            return_code=124,
            stdout=_text_output(exc.stdout),
            stderr=f"command timed out after {timeout_seconds} seconds",
            duration_seconds=time.perf_counter() - started,
        )
    except OSError as exc:
        return CommandExecutionResult(
            return_code=127,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
            duration_seconds=time.perf_counter() - started,
        )


def _subprocess_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    if argv[0] == "agent-harness":
        return [sys.executable, "-m", "agent_harness", *argv[1:]]
    if argv[0] == "python":
        return [sys.executable, *argv[1:]]
    return argv


def _text_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _safe_output_summary(value: str) -> str:
    summary = value[:SUMMARY_LIMIT]
    if len(value) > SUMMARY_LIMIT:
        summary += "\n[truncated]"
    summary = re.sub(
        r"\b[A-Za-z]:[\\/][^\s\"']+",
        "[redacted-path]",
        summary,
    )
    summary = re.sub(
        r"(?i)\b[A-Z0-9_]*(?:TOKEN|SECRET|API[_-]?KEY|PASSWORD)[A-Z0-9_]*\s*[:=]\s*\S+",
        "[redacted-secret]",
        summary,
    )
    return summary
