from __future__ import annotations

import json
from pathlib import Path

from agent_harness.config import dump_model, load_config, load_model
from agent_harness.model import DeterministicMockModel
from agent_harness.policy import PolicyEngine, load_policy
from agent_harness.retrieval import LexicalRetriever, build_context_manifest
from agent_harness.schemas import (
    ApprovalRecord,
    Checkpoint,
    RunSummary,
    TaskSpec,
    ToolCall,
    ToolObservation,
)
from agent_harness.storage import RunStore, make_event
from agent_harness.tools import ToolExecutor
from agent_harness.utils import hash_file, new_run_id, now_utc, sha256_json, stable_id


class HarnessRuntime:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.config = load_config(self.project_root)
        self.artifact_root = self.project_root / self.config.artifact_root

    def run_task(
        self,
        task_path: Path,
        profile_name: str | None = None,
        auto_approve: bool = False,
        dry_run: bool = False,
    ) -> RunSummary:
        task = load_model(task_path, TaskSpec)
        selected_profile = profile_name or task.policy_profile or self.config.default_policy
        profile = load_policy(self.project_root, selected_profile)
        policy = PolicyEngine(self.project_root, profile)
        run_id = new_run_id(task.task_id)
        store = RunStore(self.artifact_root, run_id)
        started_at = now_utc()
        store.append_event(make_event(run_id, "run_started", {"task_id": task.task_id}))
        dump_model(store.run_dir / "task.json", task)
        dump_model(store.run_dir / "policy.json", profile)

        retriever = LexicalRetriever(self.artifact_root / "indexes" / "documents.jsonl")
        context = build_context_manifest(self.project_root, run_id, task, policy, retriever)
        manifest = context.manifest
        store.write_model("context_manifest.json", manifest)
        for source_path in task.target_paths:
            decision = policy.evaluate_context_source(source_path)
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {
                        "operation": "context_source",
                        "path": source_path,
                        "decision": decision.model_dump(mode="json"),
                    },
                )
            )
        for source_path, decision in context.retrieval_decisions:
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {
                        "operation": "retrieval_source",
                        "path": source_path,
                        "decision": decision.model_dump(mode="json"),
                    },
                )
            )
        store.append_event(
            make_event(
                run_id,
                "context_manifest_created",
                {"manifest_id": manifest.manifest_id, "chunks": len(manifest.chunks)},
            )
        )

        checkpoint = Checkpoint(
            checkpoint_id=stable_id("checkpoint", run_id, task.task_id, manifest.manifest_id),
            run_id=run_id,
            task_hash=sha256_json(task.model_dump(mode="json")),
            manifest_hash=sha256_json(manifest.model_dump(mode="json")),
            policy_hash=policy.profile_hash(),
            previous_event_hash=store.event_log_hash(),
        )
        checkpoint_hash = checkpoint.checkpoint_hash()
        store.write_model(f"checkpoints/{checkpoint.checkpoint_id}.json", checkpoint)
        store.write_data("checkpoint-index.json", {"latest": checkpoint.checkpoint_id})
        store.append_event(
            make_event(
                run_id,
                "checkpoint_created",
                {
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "checkpoint_hash": checkpoint_hash,
                },
            )
        )

        executor = ToolExecutor(self.project_root, policy)
        model = DeterministicMockModel()
        observations: list[ToolObservation] = []
        status = "dry_run" if dry_run else "completed"
        approvals: list[str] = []

        for call in model.initial_actions(task, manifest):
            store.append_event(
                make_event(run_id, "model_action", {"call": call.model_dump(mode="json")})
            )
            observation, decision = executor.execute(
                call, task, checkpoint_hash, run_id=run_id, dry_run=False
            )
            observations.append(observation)
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {"action_id": call.action_id, "decision": decision.model_dump(mode="json")},
                )
            )
            store.append_event(
                make_event(
                    run_id,
                    "tool_observation",
                    {"observation": observation.model_dump(mode="json")},
                )
            )

        for call in model.next_actions(task, manifest, observations):
            store.append_event(
                make_event(run_id, "model_action", {"call": call.model_dump(mode="json")})
            )
            approval = None
            if call.tool_name == "patch_file":
                proposed_hash = executor.proposed_effect_hash(call)
                approval = ApprovalRecord(
                    approval_id=stable_id("approval", run_id, call.action_id),
                    run_id=run_id,
                    action_id=call.action_id,
                    tool_name=call.tool_name,
                    arguments_hash=call.arguments_hash(),
                    policy_profile=policy.profile.name,
                    checkpoint_hash=checkpoint_hash,
                    proposed_effect_hash=proposed_hash,
                    status="approved" if auto_approve and not dry_run else "pending",
                    decided_at=now_utc() if auto_approve and not dry_run else None,
                    actor="auto-approve" if auto_approve and not dry_run else None,
                )
            observation, decision = executor.execute(
                call,
                task,
                checkpoint_hash,
                run_id=run_id,
                approval=approval if approval and approval.status == "approved" else None,
                dry_run=False,
            )
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {"action_id": call.action_id, "decision": decision.model_dump(mode="json")},
                )
            )
            if call.tool_name == "patch_file":
                store.write_action(
                    call.action_id,
                    {
                        "call": call.model_dump(mode="json"),
                        "checkpoint_hash": checkpoint_hash,
                        "policy_profile": policy.profile.name,
                        "proposed_effect_hash": executor.proposed_effect_hash(call),
                        "observation": observation.model_dump(mode="json"),
                    },
                )
                assert approval is not None
                store.write_approval(approval)
                approvals.append(approval.action_id)
                store.append_event(
                    make_event(
                        run_id,
                        "approval_recorded",
                        {"approval": approval.model_dump(mode="json")},
                    )
                )
            store.append_event(
                make_event(
                    run_id,
                    "tool_observation",
                    {"observation": observation.model_dump(mode="json")},
                )
            )
            observations.append(observation)
            if observation.status == "pending_approval":
                status = "dry_run" if dry_run else "paused"
                break
            if not observation.success:
                status = "failed"
                break

        artifact_paths = {
            "run_dir": store.run_dir,
            "state": store.db_path,
            "task": store.run_dir / "task.json",
            "policy": store.run_dir / "policy.json",
            "events": store.events_path,
            "context_manifest": store.run_dir / "context_manifest.json",
            "checkpoint": store.run_dir / "checkpoints" / f"{checkpoint.checkpoint_id}.json",
            "checkpoint_index": store.run_dir / "checkpoint-index.json",
            "summary": store.run_dir / "summary.json",
            "artifact_index": store.run_dir / "artifact-index.json",
        }
        artifacts = {
            name: self._project_relative(path) for name, path in artifact_paths.items()
        }
        store.append_event(make_event(run_id, "run_finished", {"status": status}))
        summary = RunSummary(
            run_id=run_id,
            task_id=task.task_id,
            status=status,  # type: ignore[arg-type]
            events_count=store.event_count(),
            approvals=approvals,
            artifacts=artifacts,
            started_at=started_at,
            message=(
                "run paused for approval"
                if status == "paused"
                else "dry run complete"
                if status == "dry_run"
                else "run complete"
            ),
        )
        store.write_summary(summary)
        artifact_hashes = {
            name: hash_file(path)
            for name, path in artifact_paths.items()
            if path.is_file() and name not in {"artifact_index", "state"}
        }
        store.write_data(
            "artifact-index.json",
            {
                "run_id": run_id,
                "artifacts": artifacts,
                "artifact_hashes": artifact_hashes,
            },
        )
        return summary

    def _project_relative(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()


def approve_action(
    project_root: Path,
    run_id: str,
    action_id: str,
    decision: str,
    actor: str,
    reason: str | None = None,
) -> ApprovalRecord:
    runtime = HarnessRuntime(project_root)
    store = RunStore.open_existing(runtime.artifact_root, run_id)
    approval = store.read_approval(action_id)
    if approval.status != "pending":
        raise ValueError(f"approval is already {approval.status}")
    updated = approval.model_copy(
        update={
            "status": "approved" if decision == "approve" else "denied",
            "decided_at": now_utc(),
            "actor": actor,
            "reason": reason,
        }
    )
    store.write_approval(updated)
    store.append_event(
        make_event(run_id, "approval_decided", {"approval": updated.model_dump(mode="json")})
    )
    if decision != "approve":
        _finalize_resumed_run(store, "failed")
        return updated

    task = load_model(store.run_dir / "task.json", TaskSpec)
    profile = load_policy(project_root, updated.policy_profile)
    policy = PolicyEngine(project_root, profile)
    executor = ToolExecutor(project_root, policy)
    action_record = store.read_action(action_id)
    call = ToolCall.model_validate_json(json.dumps(action_record["call"]))
    observation, policy_decision = executor.execute(
        call,
        task,
        updated.checkpoint_hash,
        run_id=run_id,
        approval=updated,
        dry_run=False,
    )
    store.append_event(
        make_event(
            run_id,
            "policy_decision",
            {"action_id": call.action_id, "decision": policy_decision.model_dump(mode="json")},
        )
    )
    store.append_event(
        make_event(
            run_id,
            "tool_observation",
            {"observation": observation.model_dump(mode="json")},
        )
    )
    action_record["observation"] = observation.model_dump(mode="json")
    store.write_action(action_id, action_record)
    _finalize_resumed_run(store, "completed" if observation.success else "failed")
    return updated


def _finalize_resumed_run(store: RunStore, final_status: str) -> None:
    store.append_event(make_event(store.run_id, "run_finished", {"status": final_status}))
    previous = load_model(store.run_dir / "summary.json", RunSummary)
    summary = previous.model_copy(
        update={
            "status": final_status,
            "events_count": store.event_count(),
            "ended_at": now_utc(),
            "message": "run complete" if final_status == "completed" else "run failed",
        }
    )
    store.write_summary(summary)
