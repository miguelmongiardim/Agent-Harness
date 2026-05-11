from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from agent_harness.review.schema import (
    ArtifactCleanupCandidate,
    ArtifactCleanupPlan,
    ArtifactInventory,
    ArtifactInventoryItem,
    ReviewArtifactsResult,
)
from agent_harness.utils import now_utc, write_json

RELEASE_TEMP_PREFIXES = (
    "package-check-",
    "template-pack-acceptance-",
    "orchestration-workflow-",
    "mcp-boundary-",
)


def build_artifact_review(
    project_root: Path,
    *,
    older_than_days: int = 7,
) -> ReviewArtifactsResult:
    if older_than_days < 0:
        raise ValueError("--older-than-days must be non-negative")
    generated_at = now_utc()
    inventory, cleanup_plan = _build_inventory_and_cleanup(
        project_root,
        generated_at=generated_at,
        older_than_days=older_than_days,
    )
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    review_root = project_root / ".agent-harness" / "review"
    inventory_path = review_root / f"artifact-inventory-{stamp}.json"
    cleanup_path = review_root / f"artifact-cleanup-plan-{stamp}.json"
    write_json(inventory_path, inventory.model_dump(mode="json"))
    write_json(cleanup_path, cleanup_plan.model_dump(mode="json"))
    return ReviewArtifactsResult(
        generated_at=generated_at.isoformat(),
        inventory_ref=_project_relative(project_root, inventory_path),
        cleanup_plan_ref=_project_relative(project_root, cleanup_path),
        candidate_count=len(cleanup_plan.candidates),
        protected_count=cleanup_plan.protected_count,
    )


def _build_inventory_and_cleanup(
    project_root: Path,
    *,
    generated_at: datetime,
    older_than_days: int,
) -> tuple[ArtifactInventory, ArtifactCleanupPlan]:
    items: list[ArtifactInventoryItem] = []
    candidates: list[ArtifactCleanupCandidate] = []
    tracked_paths = _tracked_paths(project_root)
    for path in _inventory_paths(project_root):
        relative = _project_relative(project_root, path)
        artifact_kind = _artifact_kind(relative, path)
        candidate_kind = _candidate_kind(relative, path)
        age_days = _age_days(generated_at, path)
        contains_tracked_path = _contains_tracked_path(relative, tracked_paths)
        is_candidate = (
            candidate_kind is not None and age_days > older_than_days and not contains_tracked_path
        )
        protected = not is_candidate
        protection_reason = (
            None
            if is_candidate
            else _protection_reason(
                relative,
                artifact_kind,
                contains_tracked_path=contains_tracked_path,
            )
        )
        items.append(
            ArtifactInventoryItem(
                path=relative,
                artifact_kind=candidate_kind or artifact_kind,
                size_bytes=_size_bytes(path),
                modified_at=_modified_at(path),
                protected=protected,
                protection_reason=protection_reason,
            )
        )
        if is_candidate and candidate_kind is not None:
            candidates.append(
                ArtifactCleanupCandidate(
                    path=relative,
                    artifact_kind=candidate_kind,
                    age_days=round(age_days, 2),
                    reason=(
                        "Recognized generated work directory older than "
                        f"{older_than_days} days; dry-run only."
                    ),
                )
            )
    inventory = ArtifactInventory(
        generated_at=generated_at.isoformat(),
        root=".",
        items=items,
    )
    cleanup_plan = ArtifactCleanupPlan(
        generated_at=generated_at.isoformat(),
        dry_run=True,
        older_than_days=older_than_days,
        candidates=candidates,
        protected_count=sum(1 for item in items if item.protected),
    )
    return inventory, cleanup_plan


def _inventory_paths(project_root: Path) -> list[Path]:
    roots = [
        project_root / ".agent-harness",
        project_root / "dist",
        project_root / "docs",
        project_root / "src",
        project_root / "policies",
    ]
    files = [
        project_root / "agent-harness.yaml",
        project_root / "pyproject.toml",
        project_root / "README.md",
    ]
    paths: set[Path] = set()
    for root in roots:
        if root.exists():
            paths.add(root)
            paths.update(root.rglob("*"))
    for file_path in files:
        if file_path.exists():
            paths.add(file_path)
    return sorted(paths, key=lambda path: _project_relative(project_root, path))


def _candidate_kind(relative: str, path: Path) -> str | None:
    if not path.is_dir():
        return None
    parts = PurePosixPath(relative).parts
    if len(parts) == 3 and parts[:2] == (".agent-harness", "eval-work"):
        return "eval_work_directory"
    if (
        len(parts) == 3
        and parts[:2] == (".agent-harness", "release")
        and any(parts[2].startswith(prefix) for prefix in RELEASE_TEMP_PREFIXES)
    ):
        return "release_work_directory"
    if (
        len(parts) == 3
        and parts[:2] == (".agent-harness", "template-validation")
        and parts[2].startswith("work-")
    ):
        return "template_validation_work_directory"
    if len(parts) == 5 and parts[:3] == (".agent-harness", "benchmarks", "workspaces"):
        return "benchmark_workspace"
    return None


def _artifact_kind(relative: str, path: Path) -> str:
    parts = PurePosixPath(relative).parts
    if not parts:
        return "project_root"
    if parts[0] == ".agent-harness":
        if len(parts) > 1:
            return {
                "runs": "run_evidence",
                "release": "release_artifact",
                "evidence": "evidence_pack",
                "governance": "governance_export",
                "review": "review_evidence",
                "evals": "eval_report",
                "eval-work": "eval_work",
                "indexes": "retrieval_index",
                "benchmarks": "benchmark_artifact",
                "template-validation": "template_validation_artifact",
            }.get(parts[1], "generated_artifact")
        return "artifact_root"
    if parts[0] == "dist":
        return "dist_artifact"
    if parts[0] == "docs":
        return "docs"
    if parts[0] == "src":
        return "source"
    if parts[0] == "policies":
        return "policy"
    if path.name in {"agent-harness.yaml", "pyproject.toml"}:
        return "config"
    return "project_artifact"


def _protection_reason(
    relative: str,
    artifact_kind: str,
    *,
    contains_tracked_path: bool = False,
) -> str:
    if contains_tracked_path:
        return "tracked files are protected"
    if relative.startswith(".agent-harness/runs/"):
        return "run evidence is protected"
    if relative.startswith(".agent-harness/release/evidence/"):
        return "release evidence is protected"
    return f"{artifact_kind} is protected by default"


def _tracked_paths(project_root: Path) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if completed.returncode != 0:
        return set()
    return {
        line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()
    }


def _contains_tracked_path(relative: str, tracked_paths: set[str]) -> bool:
    if not tracked_paths:
        return False
    prefix = f"{relative.rstrip('/')}/"
    return relative in tracked_paths or any(path.startswith(prefix) for path in tracked_paths)


def _age_days(now: datetime, path: Path) -> float:
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return (now - modified).total_seconds() / 86400


def _modified_at(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def _project_relative(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root.resolve()).as_posix()
