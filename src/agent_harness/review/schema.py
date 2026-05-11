from __future__ import annotations

from typing import Literal

from agent_harness.schema_base import StrictModel

ReviewDurationClass = Literal["fast", "moderate", "slow", "release"]


class ReviewProfileCommand(StrictModel):
    command_id: str
    command: str
    argv: list[str]
    required: bool
    expected_duration_class: ReviewDurationClass
    mutates_artifacts: bool
    evidence_expectations: list[str]


class ReviewProfile(StrictModel):
    profile_id: str
    title: str
    description: str
    expected_duration_class: ReviewDurationClass
    commands: list[ReviewProfileCommand]


class ReviewProfileCatalog(StrictModel):
    schema_version: Literal["review_profile_catalog.v1"] = "review_profile_catalog.v1"
    generated_at: str
    profiles: list[ReviewProfile]


ReviewAvailabilityStatus = Literal["available", "missing"]
ReviewEvidenceStatus = Literal["present", "missing"]


class ReviewCommandStatus(StrictModel):
    command_id: str
    command: str
    required: bool
    availability_status: ReviewAvailabilityStatus
    evidence_status: ReviewEvidenceStatus
    evidence_refs: list[str]
    next_actions: list[str]


class ReviewMissingEvidence(StrictModel):
    command_id: str
    command: str
    required: bool
    action: str


class ReviewNextAction(StrictModel):
    command_id: str
    command: str
    action: str


class ReviewStatus(StrictModel):
    schema_version: Literal["review_status.v1"] = "review_status.v1"
    generated_at: str
    profile_id: str
    expected_duration_class: ReviewDurationClass
    commands: list[ReviewCommandStatus]
    missing_evidence: list[ReviewMissingEvidence]
    next_actions: list[ReviewNextAction]


ReviewRunStatus = Literal["passed", "failed"]
ReviewCommandRunStatus = Literal["passed", "failed", "skipped"]


class ReviewRunCommandResult(StrictModel):
    command_id: str
    command: str
    argv: list[str]
    required: bool
    status: ReviewCommandRunStatus
    return_code: int | None
    duration_seconds: float
    stdout_summary: str
    stderr_summary: str
    evidence_refs: list[str]
    skipped_reason: str | None = None
    next_actions: list[str]


class ReviewRun(StrictModel):
    schema_version: Literal["review_run.v1"] = "review_run.v1"
    generated_at: str
    profile_id: str
    status: ReviewRunStatus
    commands: list[ReviewRunCommandResult]
    artifact: str
    next_actions: list[ReviewNextAction]


class ArtifactInventoryItem(StrictModel):
    path: str
    artifact_kind: str
    size_bytes: int
    modified_at: str
    protected: bool
    protection_reason: str | None = None


class ArtifactInventory(StrictModel):
    schema_version: Literal["artifact_inventory.v1"] = "artifact_inventory.v1"
    generated_at: str
    root: str
    items: list[ArtifactInventoryItem]


class ArtifactCleanupCandidate(StrictModel):
    path: str
    artifact_kind: str
    age_days: float
    reason: str


class ArtifactCleanupPlan(StrictModel):
    schema_version: Literal["artifact_cleanup_plan.v1"] = "artifact_cleanup_plan.v1"
    generated_at: str
    dry_run: bool
    older_than_days: int
    candidates: list[ArtifactCleanupCandidate]
    protected_count: int


class ReviewArtifactsResult(StrictModel):
    schema_version: Literal["review_artifacts.v1"] = "review_artifacts.v1"
    generated_at: str
    inventory_ref: str
    cleanup_plan_ref: str
    candidate_count: int
    protected_count: int
