from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agent_harness.orchestration.schema import (
    OrchestrationApprovalRecord,
    OrchestrationArtifactIndex,
    OrchestrationEvent,
    OrchestrationPlan,
    OrchestrationSummary,
)
from agent_harness.utils import hash_file, load_json, stable_id, write_json


class OrchestrationStore:
    def __init__(
        self,
        project_root: Path,
        artifact_root: Path,
        orchestration_id: str,
        create: bool = True,
    ) -> None:
        self.project_root = project_root.resolve()
        self.artifact_root = artifact_root
        self.orchestration_id = orchestration_id
        self.orchestration_dir = artifact_root / "orchestrations" / orchestration_id
        self.events_path = self.orchestration_dir / "events.jsonl"
        if create:
            if self.orchestration_dir.exists():
                raise FileExistsError(f"orchestration already exists: {orchestration_id}")
            (self.orchestration_dir / "children").mkdir(parents=True, exist_ok=True)

    @classmethod
    def open_existing(
        cls, project_root: Path, artifact_root: Path, orchestration_id: str
    ) -> OrchestrationStore:
        orchestration_dir = artifact_root / "orchestrations" / orchestration_id
        if not orchestration_dir.exists():
            raise FileNotFoundError(f"orchestration not found: {orchestration_id}")
        return cls(project_root, artifact_root, orchestration_id, create=False)

    def write_model(self, relative: str, model: BaseModel) -> Path:
        path = self.orchestration_dir / relative
        write_json(path, model.model_dump(mode="json"))
        return path

    def write_data(self, relative: str, data: dict[str, Any]) -> Path:
        path = self.orchestration_dir / relative
        write_json(path, data)
        return path

    def read_data(self, relative: str) -> dict[str, Any]:
        loaded = load_json(self.orchestration_dir / relative)
        if not isinstance(loaded, dict):
            raise ValueError(f"{relative} did not contain an object")
        return loaded

    def read_handoffs(self) -> list[dict[str, Any]]:
        handoff_dir = self.orchestration_dir / "handoffs"
        if not handoff_dir.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(handoff_dir.glob("*.json")):
            loaded = load_json(path)
            if not isinstance(loaded, dict):
                raise ValueError(f"{path.name} did not contain an object")
            records.append(loaded)
        return records

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        sequence = self.event_count() + 1
        event = OrchestrationEvent(
            event_id=stable_id(
                "orchestration-event",
                self.orchestration_id,
                sequence,
                event_type,
                payload,
            ),
            orchestration_id=self.orchestration_id,
            type=event_type,
            payload=payload,
        )
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")

    def events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [
            json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()
        ]

    def event_count(self) -> int:
        return len(self.events())

    def write_summary(self, summary: OrchestrationSummary) -> Path:
        return self.write_model("summary.json", summary)

    def read_summary(self) -> OrchestrationSummary:
        return OrchestrationSummary.model_validate_json(
            (self.orchestration_dir / "summary.json").read_text(encoding="utf-8")
        )

    def read_plan(self) -> OrchestrationPlan:
        return OrchestrationPlan.model_validate_json(
            (self.orchestration_dir / "orchestration-plan.json").read_text(encoding="utf-8")
        )

    def write_approval(self, approval: OrchestrationApprovalRecord) -> Path:
        return self.write_model(f"approvals/{approval.action_id}.json", approval)

    def read_approval(self, action_id: str) -> OrchestrationApprovalRecord:
        return OrchestrationApprovalRecord.model_validate_json(
            (self.orchestration_dir / "approvals" / f"{action_id}.json").read_text(encoding="utf-8")
        )

    def approvals(self) -> list[dict[str, Any]]:
        approval_dir = self.orchestration_dir / "approvals"
        if not approval_dir.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(approval_dir.glob("*.json")):
            loaded = load_json(path)
            if not isinstance(loaded, dict):
                raise ValueError(f"{path.name} did not contain an object")
            records.append(loaded)
        return records

    def write_artifact_index(self, artifacts: dict[str, str]) -> OrchestrationArtifactIndex:
        artifact_hashes: dict[str, str] = {}
        for name, reference in artifacts.items():
            if name == "artifact_index":
                continue
            path = self.project_root / reference
            if path.is_file():
                artifact_hashes[name] = hash_file(path)
        index = OrchestrationArtifactIndex(
            orchestration_id=self.orchestration_id,
            artifacts=artifacts,
            artifact_hashes=artifact_hashes,
        )
        self.write_model("artifact-index.json", index)
        return index

    def project_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()
