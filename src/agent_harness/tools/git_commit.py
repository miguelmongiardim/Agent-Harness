from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from agent_harness.policy import PolicyEngine
from agent_harness.storage import RunStore
from agent_harness.storage.schema import ApprovalRecord
from agent_harness.tasks.schema import TaskSpec
from agent_harness.tools.schema import GitCommitPlan, ToolCall
from agent_harness.utils import hash_file, now_utc, sha256_json, sha256_text, stable_id


def plan_git_commit(
    project_root: Path,
    store: RunStore,
    task: TaskSpec,
    policy: PolicyEngine,
    checkpoint_hash: str,
    final_message: str,
) -> tuple[GitCommitPlan, ApprovalRecord]:
    message = final_message.strip()
    if not message:
        raise ValueError("git_commit requires a non-empty final message")

    _ensure_git_worktree(project_root)
    _ensure_no_staged_changes(project_root)
    _ensure_success_checks_passed(store, task)
    approved_patches = _approved_patch_bindings(store)
    if not approved_patches:
        raise ValueError("git_commit requires at least one approved patch")

    file_set = sorted({patch["path"] for patch in approved_patches})
    content_hashes = _current_content_hashes(project_root, approved_patches)
    parent_head = _git_stdout(project_root, "rev-parse", "HEAD")
    diff = _approved_staged_diff(project_root, file_set)
    message_hash = sha256_text(message)
    effect_payload = _git_commit_effect_payload(
        parent_head=parent_head,
        file_set=file_set,
        content_hashes=content_hashes,
        diff_hash=sha256_text(diff),
        final_message_hash=message_hash,
        policy_profile=policy.profile.name,
        checkpoint_hash=checkpoint_hash,
        approved_patch_action_ids=[patch["action_id"] for patch in approved_patches],
    )
    arguments_payload = _git_commit_arguments_payload(message, message_hash)
    action_id = stable_id("action", store.run_id, "git_commit", arguments_payload, effect_payload)
    plan = GitCommitPlan(
        run_id=store.run_id,
        action_id=action_id,
        parent_head=parent_head,
        file_set=file_set,
        content_hashes=content_hashes,
        diff=diff,
        diff_hash=str(effect_payload["diff_hash"]),
        final_message=message,
        final_message_hash=message_hash,
        policy_profile=policy.profile.name,
        checkpoint_hash=checkpoint_hash,
        approved_patch_action_ids=[patch["action_id"] for patch in approved_patches],
    )
    approval = ApprovalRecord(
        approval_id=stable_id("approval", store.run_id, action_id),
        run_id=store.run_id,
        action_id=action_id,
        tool_name="git_commit",
        arguments_hash=sha256_json(arguments_payload),
        policy_profile=policy.profile.name,
        checkpoint_hash=checkpoint_hash,
        proposed_effect_hash=sha256_json(effect_payload),
    )
    return plan, approval


def validate_git_commit_approval(
    approval: ApprovalRecord,
    plan: GitCommitPlan,
    run_id: str,
    policy_profile: str,
) -> None:
    arguments_payload = _git_commit_arguments_payload(
        plan.final_message,
        plan.final_message_hash,
    )
    effect_payload = _git_commit_effect_payload(
        parent_head=plan.parent_head,
        file_set=plan.file_set,
        content_hashes=plan.content_hashes,
        diff_hash=plan.diff_hash,
        final_message_hash=plan.final_message_hash,
        policy_profile=plan.policy_profile,
        checkpoint_hash=plan.checkpoint_hash,
        approved_patch_action_ids=plan.approved_patch_action_ids,
    )
    expected = {
        "run_id": run_id,
        "action_id": stable_id("action", run_id, "git_commit", arguments_payload, effect_payload),
        "tool_name": "git_commit",
        "arguments_hash": sha256_json(arguments_payload),
        "policy_profile": policy_profile,
        "checkpoint_hash": plan.checkpoint_hash,
        "proposed_effect_hash": sha256_json(effect_payload),
    }
    actual = {
        "run_id": approval.run_id,
        "action_id": approval.action_id,
        "tool_name": approval.tool_name,
        "arguments_hash": approval.arguments_hash,
        "policy_profile": approval.policy_profile,
        "checkpoint_hash": approval.checkpoint_hash,
        "proposed_effect_hash": approval.proposed_effect_hash,
    }
    if actual != expected:
        raise ValueError("git commit approval binding does not match repository state")


def execute_git_commit(project_root: Path, plan: GitCommitPlan) -> str:
    _ensure_git_worktree(project_root)
    current_head = _git_stdout(project_root, "rev-parse", "HEAD")
    if current_head != plan.parent_head:
        raise ValueError("parent HEAD changed before git_commit execution")
    _ensure_no_staged_changes(project_root)
    for path, expected_hash in plan.content_hashes.items():
        resolved = project_root / path
        if not resolved.exists():
            raise ValueError(f"approved file missing before git_commit execution: {path}")
        actual_hash = hash_file(resolved)
        if actual_hash != expected_hash:
            raise ValueError(f"approved file content changed before git_commit execution: {path}")

    committed = False
    try:
        _git(project_root, "add", "--", *plan.file_set)
        staged = _staged_paths(project_root)
        if staged != plan.file_set:
            raise ValueError("staged changes do not match approved git_commit file set")
        staged_diff = _git_stdout(
            project_root,
            "diff",
            "--cached",
            "--binary",
            "--",
            *plan.file_set,
        )
        if sha256_text(staged_diff) != plan.diff_hash:
            raise ValueError("approved diff changed before git_commit execution")
        _git(project_root, "commit", "-m", plan.final_message)
        committed = True
        return _git_stdout(project_root, "rev-parse", "HEAD")
    finally:
        if not committed:
            _git(project_root, "reset", "--", *plan.file_set, check=False)


def bind_committed_hash(plan: GitCommitPlan, commit_hash: str) -> GitCommitPlan:
    return plan.model_copy(
        update={
            "commit_hash": commit_hash,
            "committed_at": now_utc(),
        }
    )


def _approved_patch_bindings(store: RunStore) -> list[dict[str, str]]:
    patches: list[dict[str, str]] = []
    for approval_path in sorted((store.run_dir / "approvals").glob("*.json")):
        approval = ApprovalRecord.model_validate_json(approval_path.read_text(encoding="utf-8"))
        if approval.tool_name != "patch_file" or approval.status != "approved":
            continue
        action = store.read_action(approval.action_id)
        call = ToolCall.model_validate_json(json.dumps(action["call"]))
        if call.tool_name != "patch_file":
            raise ValueError("approved patch action changed before git_commit planning")
        observation = action.get("observation", {})
        output = observation.get("output", {}) if isinstance(observation, dict) else {}
        if (
            observation.get("status") != "ok"
            or not observation.get("success")
            or output.get("path") != call.arguments.get("path")
        ):
            raise ValueError("git_commit requires approved patches to be applied successfully")
        if call.arguments_hash() != approval.arguments_hash:
            raise ValueError("approved patch action binding changed before git_commit planning")
        action_effect_hash = action.get("proposed_effect_hash")
        if action_effect_hash != approval.proposed_effect_hash:
            raise ValueError("approved patch effect binding changed before git_commit planning")
        path = str(output["path"])
        after_hash = output.get("after_hash")
        if not isinstance(after_hash, str):
            raise ValueError("approved patch did not record an after_hash")
        patches.append(
            {
                "action_id": approval.action_id,
                "path": path,
                "after_hash": after_hash,
            }
        )
    return patches


def _current_content_hashes(
    project_root: Path,
    approved_patches: list[dict[str, str]],
) -> dict[str, str]:
    content_hashes: dict[str, str] = {}
    for patch in approved_patches:
        path = patch["path"]
        resolved = project_root / path
        if not resolved.exists():
            raise ValueError(f"approved patch target missing before git_commit planning: {path}")
        approved_text_hash = sha256_text(resolved.read_text(encoding="utf-8"))
        if approved_text_hash != patch["after_hash"]:
            raise ValueError(f"approved patch target changed before git_commit planning: {path}")
        current_hash = hash_file(resolved)
        existing = content_hashes.get(path)
        if existing is not None and existing != current_hash:
            raise ValueError(f"conflicting approved hashes for git_commit target: {path}")
        content_hashes[path] = current_hash
    return {path: content_hashes[path] for path in sorted(content_hashes)}


def _ensure_success_checks_passed(store: RunStore, task: TaskSpec) -> None:
    if not task.test_commands:
        return
    passed_commands: set[tuple[str, ...]] = set()
    for event in store.events():
        if event.get("type") != "tool_observation":
            continue
        observation = event.get("payload", {}).get("observation", {})
        if observation.get("tool_name") != "run_tests" or not observation.get("success"):
            continue
        command = observation.get("output", {}).get("command")
        if isinstance(command, list) and all(isinstance(part, str) for part in command):
            passed_commands.add(tuple(command))
    missing = [command for command in task.test_commands if tuple(command) not in passed_commands]
    if missing:
        raise ValueError("git_commit requires required test commands to pass before commit")


def _approved_staged_diff(project_root: Path, file_set: list[str]) -> str:
    try:
        _git(project_root, "add", "--", *file_set)
        staged = _staged_paths(project_root)
        if staged != file_set:
            raise ValueError("staged changes do not match approved git_commit file set")
        diff = _git_stdout(project_root, "diff", "--cached", "--binary", "--", *file_set)
    finally:
        _git(project_root, "reset", "--", *file_set, check=False)
    if not diff:
        raise ValueError("git_commit approved file set has no diff to commit")
    return diff


def _ensure_git_worktree(project_root: Path) -> None:
    inside = _git_stdout(project_root, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        raise ValueError("git_commit requires a git worktree")
    top_level = Path(_git_stdout(project_root, "rev-parse", "--show-toplevel")).resolve()
    if top_level != project_root.resolve():
        raise ValueError("git_commit must run from the git worktree root")


def _ensure_no_staged_changes(project_root: Path) -> None:
    staged = _staged_paths(project_root)
    if staged:
        raise ValueError("git_commit denied because staged changes already exist")


def _staged_paths(project_root: Path) -> list[str]:
    output = _git_stdout(project_root, "diff", "--cached", "--name-only")
    return sorted(path.replace("\\", "/") for path in output.splitlines() if path)


def _git_commit_arguments_payload(final_message: str, final_message_hash: str) -> dict[str, str]:
    return {
        "final_message": final_message,
        "final_message_hash": final_message_hash,
    }


def _git_commit_effect_payload(
    *,
    parent_head: str,
    file_set: list[str],
    content_hashes: dict[str, str],
    diff_hash: str,
    final_message_hash: str,
    policy_profile: str,
    checkpoint_hash: str,
    approved_patch_action_ids: list[str],
) -> dict[str, Any]:
    return {
        "parent_head": parent_head,
        "file_set": file_set,
        "content_hashes": content_hashes,
        "diff_hash": diff_hash,
        "final_message_hash": final_message_hash,
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
        "approved_patch_action_ids": approved_patch_action_ids,
    }


def _git_stdout(project_root: Path, *args: str) -> str:
    return _git(project_root, *args).stdout.strip()


def _git(
    project_root: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return completed
