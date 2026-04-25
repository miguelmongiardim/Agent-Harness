from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agent_harness.schemas import ApprovalRecord, RunEvent, RunSummary
from agent_harness.utils import load_json, stable_id, write_json


class RunStore:
    def __init__(self, artifact_root: Path, run_id: str, create: bool = True) -> None:
        self.artifact_root = artifact_root
        self.run_id = run_id
        self.run_dir = artifact_root / "runs" / run_id
        self.events_path = self.run_dir / "events.jsonl"
        self.db_path = artifact_root / "state.sqlite3"
        if create:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / "actions").mkdir(exist_ok=True)
            (self.run_dir / "approvals").mkdir(exist_ok=True)
            (self.run_dir / "checkpoints").mkdir(exist_ok=True)
            self._init_db()

    @classmethod
    def open_existing(cls, artifact_root: Path, run_id: str) -> "RunStore":
        run_dir = artifact_root / "runs" / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"run not found: {run_id}")
        return cls(artifact_root, run_id, create=False)

    def write_model(self, relative: str, model: BaseModel) -> Path:
        path = self.run_dir / relative
        write_json(path, model.model_dump(mode="json"))
        return path

    def write_data(self, relative: str, data: dict[str, Any]) -> Path:
        path = self.run_dir / relative
        write_json(path, data)
        return path

    def read_data(self, relative: str) -> dict[str, Any]:
        loaded = load_json(self.run_dir / relative)
        if not isinstance(loaded, dict):
            raise ValueError(f"{relative} did not contain an object")
        return loaded

    def append_event(self, event: RunEvent) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "insert into events(event_id, run_id, type, created_at) values (?, ?, ?, ?)",
                (event.event_id, event.run_id, event.type, event.created_at.isoformat()),
            )

    def events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text(encoding="utf-8").splitlines()]

    def event_count(self) -> int:
        return len(self.events())

    def write_action(self, action_id: str, payload: dict[str, Any]) -> Path:
        return self.write_data(f"actions/{action_id}.json", payload)

    def read_action(self, action_id: str) -> dict[str, Any]:
        return self.read_data(f"actions/{action_id}.json")

    def write_approval(self, approval: ApprovalRecord) -> Path:
        path = self.write_model(f"approvals/{approval.action_id}.json", approval)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert or replace into approvals(
                    approval_id, run_id, action_id, status, path
                ) values (?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.run_id,
                    approval.action_id,
                    approval.status,
                    str(path),
                ),
            )
        return path

    def read_approval(self, action_id: str) -> ApprovalRecord:
        data = self.read_data(f"approvals/{action_id}.json")
        return ApprovalRecord.model_validate(data)

    def write_summary(self, summary: RunSummary) -> Path:
        path = self.write_model("summary.json", summary)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert or replace into runs(
                    run_id, task_id, status, created_at, updated_at, summary_path
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.task_id,
                    summary.status,
                    summary.started_at.isoformat(),
                    summary.ended_at.isoformat(),
                    str(path),
                ),
            )
        return path

    def _init_db(self) -> None:
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists runs(
                    run_id text primary key,
                    task_id text not null,
                    status text not null,
                    created_at text not null,
                    updated_at text not null,
                    summary_path text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists events(
                    event_id text primary key,
                    run_id text not null,
                    type text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists approvals(
                    approval_id text primary key,
                    run_id text not null,
                    action_id text not null,
                    status text not null,
                    path text not null
                )
                """
            )


def make_event(run_id: str, event_type: str, payload: dict[str, Any]) -> RunEvent:
    return RunEvent(
        event_id=stable_id("event", run_id, event_type, payload),
        run_id=run_id,
        type=event_type,
        payload=payload,
    )
