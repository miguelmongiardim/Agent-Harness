from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness.config import dump_model, load_config
from agent_harness.context.builder import GeneratedHandoffContext
from agent_harness.core.runtime import HarnessRuntime
from agent_harness.orchestration.policy import require_orchestration_policy
from agent_harness.orchestration.schema import (
    OrchestrationApprovalRecord,
    OrchestrationAuthority,
    OrchestrationChild,
    OrchestrationChildRun,
    OrchestrationHandoff,
    OrchestrationManifest,
    OrchestrationManifestChild,
    OrchestrationManifestHandoff,
    OrchestrationPlan,
    OrchestrationRiskSummary,
    OrchestrationSpec,
    OrchestrationStatus,
    OrchestrationSummary,
)
from agent_harness.orchestration.specs import load_orchestration_spec
from agent_harness.orchestration.store import OrchestrationStore
from agent_harness.policy import PolicyEngine, load_policy
from agent_harness.storage.schema import RunSummary
from agent_harness.tasks.schema import TaskSpec
from agent_harness.tools.schema import ToolName
from agent_harness.utils import hash_file, now_utc, sha256_text

TOOL_ORDER: list[ToolName] = [
    "read_file",
    "search_code",
    "run_tests",
    "patch_file",
    "git_status",
    "git_commit",
]
ROLE_CEILINGS: dict[str, set[ToolName]] = {
    "planner": {"read_file", "search_code"},
    "implementer": {"read_file", "search_code", "patch_file"},
    "reviewer": {"read_file", "search_code", "git_status"},
    "tester": {"read_file", "search_code", "run_tests"},
}
WRITE_TOOLS = {"patch_file"}


def run_orchestration(
    project_root: Path,
    spec_path: Path,
    *,
    profile_name: str | None = None,
    dry_run: bool = False,
) -> OrchestrationSummary:
    if not dry_run:
        raise ValueError("V11 orchestration supports --dry-run only")
    root = project_root.resolve()
    resolved_spec_path = spec_path.resolve()
    spec = load_orchestration_spec(resolved_spec_path)
    ordered_children = _dependency_order(spec)

    config = load_config(root)
    selected_profile = profile_name or config.default_policy
    profile = load_policy(root, selected_profile)
    orchestration_policy = require_orchestration_policy(profile)
    for child in ordered_children:
        if child.role not in orchestration_policy.allowed_roles:
            raise PermissionError(f"orchestration role denied by policy: {child.role}")
    policy = PolicyEngine(root, profile)
    plan = _build_plan(
        spec,
        ordered_children,
        source_spec=_project_relative_or_name(root, resolved_spec_path),
        source_spec_path=resolved_spec_path,
        policy=policy,
        policy_profile=selected_profile,
        dry_run=dry_run,
    )
    for authority in plan.children:
        if authority.denied_tools:
            denied = ", ".join(authority.denied_tools)
            raise PermissionError(
                f"child {authority.child_id} declares tools denied by role ceiling: {denied}"
            )

    artifact_root = root / config.artifact_root
    store = OrchestrationStore(root, artifact_root, spec.orchestration_id)
    started_at = now_utc()
    store.append_event(
        "orchestration_started",
        {
            "source_spec": plan.source_spec,
            "policy_profile": selected_profile,
            "dry_run": dry_run,
        },
    )
    store.append_event(
        "orchestration_spec_validated",
        {"schema_version": spec.schema_version, "children": len(spec.children)},
    )
    store.append_event(
        "orchestration_policy_allowed",
        {
            "policy_profile": selected_profile,
            "execution": orchestration_policy.execution,
            "allowed_roles": list(orchestration_policy.allowed_roles),
        },
    )
    plan_path = store.write_model("orchestration-plan.json", plan)
    store.append_event(
        "orchestration_plan_created",
        {
            "risk_summary": plan.risk_summary.model_dump(mode="json"),
            "children": [child.model_dump(mode="json") for child in plan.children],
        },
    )
    plan_artifacts = {"orchestration_plan": store.project_relative(plan_path)}
    if plan.risk_summary.requires_approval:
        approval = _plan_approval(spec.orchestration_id, selected_profile, plan)
        approval_path = store.write_approval(approval)
        store.append_event(
            "approval_recorded",
            {
                "approval": approval.model_dump(mode="json"),
                "operation": "orchestration_plan",
            },
        )
        store.append_event(
            "orchestration_paused",
            {"status": "paused", "approval": approval.action_id},
        )
        return _finalize_orchestration(
            store,
            spec,
            plan,
            status="paused",
            child_order=[],
            handoff_records=[],
            started_at=started_at,
            approvals=[approval.action_id],
            extra_artifacts={
                **plan_artifacts,
                f"approval_{approval.action_id}": store.project_relative(approval_path),
            },
        )

    return _execute_children(
        root,
        store,
        spec,
        ordered_children,
        selected_profile,
        policy,
        plan,
        started_at,
        approvals=[],
        extra_artifacts=plan_artifacts,
    )


def resume_orchestration(project_root: Path, orchestration_id: str) -> OrchestrationSummary:
    root = project_root.resolve()
    config = load_config(root)
    store = OrchestrationStore.open_existing(root, root / config.artifact_root, orchestration_id)
    previous = store.read_summary()
    if previous.status != "paused":
        raise ValueError("orchestration resume requires a paused orchestration")
    plan = store.read_plan()
    if not previous.approvals:
        raise ValueError("paused orchestration has no approval to resume")
    approval = store.read_approval(previous.approvals[-1])
    if approval.status != "approved":
        raise PermissionError("orchestration_plan approval is not approved")
    if approval.binding_hash != plan.binding_hash():
        raise PermissionError("orchestration plan binding drift detected")
    spec_path = root / plan.source_spec
    spec = load_orchestration_spec(spec_path)
    ordered_children = _dependency_order(spec)
    profile = load_policy(root, plan.policy_profile)
    policy = PolicyEngine(root, profile)
    current_plan = _build_plan(
        spec,
        ordered_children,
        source_spec=plan.source_spec,
        source_spec_path=spec_path,
        policy=policy,
        policy_profile=plan.policy_profile,
        dry_run=plan.dry_run,
    )
    if current_plan.binding_hash() != approval.binding_hash:
        raise PermissionError("orchestration plan binding drift detected")
    store.append_event(
        "orchestration_resumed",
        {"approval": approval.action_id, "policy_profile": plan.policy_profile},
    )
    return _execute_children(
        root,
        store,
        spec,
        ordered_children,
        plan.policy_profile,
        policy,
        current_plan,
        previous.started_at,
        approvals=list(previous.approvals),
        extra_artifacts=dict(previous.artifacts),
    )


def approve_orchestration_plan(
    project_root: Path,
    orchestration_id: str,
    action_id: str,
    *,
    decision: str,
    actor: str,
    reason: str | None = None,
) -> OrchestrationApprovalRecord:
    root = project_root.resolve()
    config = load_config(root)
    store = OrchestrationStore.open_existing(root, root / config.artifact_root, orchestration_id)
    approval = store.read_approval(action_id)
    if approval.status != "pending":
        raise ValueError("orchestration approval is already decided")
    if decision not in {"approve", "deny"}:
        raise ValueError("decision must be approve or deny")
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
        "approval_decided",
        {
            "approval": updated.model_dump(mode="json"),
            "operation": "orchestration_plan",
        },
    )
    return updated


def _execute_children(
    root: Path,
    store: OrchestrationStore,
    spec: OrchestrationSpec,
    ordered_children: list[OrchestrationChild],
    selected_profile: str,
    policy: PolicyEngine,
    plan: OrchestrationPlan,
    started_at: Any,
    *,
    approvals: list[str],
    extra_artifacts: dict[str, str],
) -> OrchestrationSummary:
    authority_by_child = {authority.child_id: authority for authority in plan.children}

    child_records: dict[str, OrchestrationChildRun] = {}
    child_order: list[OrchestrationChildRun] = []
    handoff_records: list[OrchestrationHandoff] = []
    handoff_artifacts: dict[str, str] = {}
    status: OrchestrationStatus = "dry_run"

    for child in ordered_children:
        handoff_contexts = [
            _write_handoff(
                store,
                policy,
                spec.orchestration_id,
                child_records[dependency],
                child,
            )
            for dependency in child.depends_on
        ]
        for handoff, _context in handoff_contexts:
            handoff_records.append(handoff)
            handoff_artifacts[f"handoff_{handoff.from_child_id}_to_{handoff.to_child_id}"] = (
                handoff.artifact
            )
            store.append_event(
                "handoff_created",
                {
                    "handoff_id": handoff.handoff_id,
                    "from_child_id": handoff.from_child_id,
                    "from_run_id": handoff.from_run_id,
                    "to_child_id": handoff.to_child_id,
                    "artifact": handoff.artifact,
                    "policy_decision_id": handoff.policy_decision_id,
                },
            )
        task = _materialize_child_task(
            spec.orchestration_id,
            child,
            selected_profile,
            authority_by_child[child.child_id].effective_tools,
        )
        task_path = store.orchestration_dir / "children" / f"{child.child_id}.task.json"
        dump_model(task_path, task)
        materialized_task_path = store.project_relative(task_path)
        store.append_event(
            "child_task_materialized",
            {
                "child_id": child.child_id,
                "role": child.role,
                "task_id": task.task_id,
                "task_path": materialized_task_path,
            },
        )
        store.append_event(
            "child_started",
            {"child_id": child.child_id, "role": child.role, "task_id": task.task_id},
        )
        child_summary = HarnessRuntime(root).run_task(
            task_path,
            profile_name=selected_profile,
            provider_name=child.provider_profile,
            dry_run=plan.dry_run,
            generated_handoffs=[context for _, context in handoff_contexts],
        )
        child_record = _child_record(child, child_summary, materialized_task_path, handoff_records)
        child_records[child.child_id] = child_record
        child_order.append(child_record)
        store.append_event(
            "child_finished",
            {
                "child_id": child.child_id,
                "run_id": child_summary.run_id,
                "status": child_summary.status,
                "run_summary_artifact": child_summary.artifacts["summary"],
            },
        )
        status = _aggregate_status(status, child_summary.status)
        if status in {"failed", "paused"}:
            break

    return _finalize_orchestration(
        store,
        spec,
        plan,
        status=status,
        child_order=child_order,
        handoff_records=handoff_records,
        started_at=started_at,
        approvals=approvals,
        extra_artifacts={**extra_artifacts, **handoff_artifacts},
    )


def _finalize_orchestration(
    store: OrchestrationStore,
    spec: OrchestrationSpec,
    plan: OrchestrationPlan,
    *,
    status: OrchestrationStatus,
    child_order: list[OrchestrationChildRun],
    handoff_records: list[OrchestrationHandoff],
    started_at: Any,
    approvals: list[str],
    extra_artifacts: dict[str, str],
) -> OrchestrationSummary:
    manifest = OrchestrationManifest(
        orchestration_id=spec.orchestration_id,
        source_spec=plan.source_spec,
        policy_profile=plan.policy_profile,
        children=[
            OrchestrationManifestChild(
                child_id=child_record.child_id,
                role=child_record.role,
                task_path=child_record.materialized_task_path,
                run_id=child_record.run_id,
                run_summary_artifact=child_record.run_summary_artifact,
            )
            for child_record in child_order
        ],
        handoffs=[
            OrchestrationManifestHandoff(
                handoff_id=handoff.handoff_id,
                from_child_id=handoff.from_child_id,
                from_run_id=handoff.from_run_id,
                to_child_id=handoff.to_child_id,
                artifact=handoff.artifact,
                policy_decision_id=handoff.policy_decision_id,
            )
            for handoff in handoff_records
        ],
    )
    manifest_path = store.write_model("manifest.json", manifest)
    store.append_event(
        "orchestration_manifest_created",
        {"manifest": store.project_relative(manifest_path), "children": len(manifest.children)},
    )
    store.append_event("orchestration_finished", {"status": status})

    artifact_index_path = store.orchestration_dir / "artifact-index.json"
    artifacts = {
        "orchestration_dir": store.project_relative(store.orchestration_dir),
        "summary": store.project_relative(store.orchestration_dir / "summary.json"),
        "events": store.project_relative(store.events_path),
        "manifest": store.project_relative(manifest_path),
        "artifact_index": store.project_relative(artifact_index_path),
        **{
            f"child_task_{child_record.child_id}": child_record.materialized_task_path
            for child_record in child_order
        },
        **extra_artifacts,
    }
    summary = OrchestrationSummary(
        orchestration_id=spec.orchestration_id,
        title=spec.title,
        source_spec=plan.source_spec,
        policy_profile=plan.policy_profile,
        status=status,
        children=child_order,
        authority=plan.children,
        events_count=store.event_count(),
        approvals=approvals,
        artifacts=artifacts,
        started_at=started_at,
        ended_at=now_utc(),
        message=_summary_message_for_status(status),
    )
    store.write_summary(summary)
    store.write_artifact_index(artifacts)
    return summary


def inspect_orchestration(project_root: Path, orchestration_id: str) -> dict[str, Any]:
    root = project_root.resolve()
    config = load_config(root)
    store = OrchestrationStore.open_existing(root, root / config.artifact_root, orchestration_id)
    return {
        "schema_version": "orchestration_inspection.v1",
        "summary": store.read_data("summary.json"),
        "events": store.events(),
        "manifest": store.read_data("manifest.json"),
        "handoffs": store.read_handoffs(),
        "approvals": store.approvals(),
        "artifact_index": store.read_data("artifact-index.json"),
    }


def _materialize_child_task(
    orchestration_id: str,
    child: OrchestrationChild,
    policy_profile: str,
    effective_tools: list[ToolName],
) -> TaskSpec:
    return TaskSpec(
        schema_version="task.v2",
        task_id=f"{orchestration_id}-{child.child_id}",
        title=child.title,
        intent=child.intent,
        policy_profile=policy_profile,
        provider_profile=child.provider_profile,
        target_paths=list(child.target_paths),
        allowed_tools=effective_tools,
        max_steps=8,
    )


def _build_plan(
    spec: OrchestrationSpec,
    ordered_children: list[OrchestrationChild],
    *,
    source_spec: str,
    source_spec_path: Path,
    policy: PolicyEngine,
    policy_profile: str,
    dry_run: bool,
) -> OrchestrationPlan:
    children = [_authority_for_child(policy, child) for child in ordered_children]
    write_capable_children = [child.child_id for child in children if child.write_capable]
    provider_children = [child.child_id for child in children if child.provider_profile is not None]
    return OrchestrationPlan(
        orchestration_id=spec.orchestration_id,
        source_spec=source_spec,
        source_spec_hash=hash_file(source_spec_path),
        policy_profile=policy_profile,
        policy_hash=policy.profile_hash(),
        dry_run=dry_run,
        children=children,
        risk_summary=OrchestrationRiskSummary(
            requires_approval=bool(write_capable_children or provider_children),
            write_capable_children=write_capable_children,
            provider_children=provider_children,
        ),
    )


def _authority_for_child(policy: PolicyEngine, child: OrchestrationChild) -> OrchestrationAuthority:
    declared = _ordered_tools(set(child.allowed_tools or TOOL_ORDER))
    role_ceiling = _ordered_tools(ROLE_CEILINGS[child.role])
    effective = _ordered_tools(
        set(declared).intersection(role_ceiling, policy.profile.allowed_tools)
    )
    denied_by_role = _ordered_tools(set(declared).difference(role_ceiling))
    return OrchestrationAuthority(
        child_id=child.child_id,
        role=child.role,
        declared_tools=declared,
        role_ceiling=role_ceiling,
        effective_tools=effective,
        denied_tools=denied_by_role,
        write_capable=bool(set(effective).intersection(WRITE_TOOLS)),
        provider_profile=child.provider_profile,
    )


def _ordered_tools(tools: set[ToolName] | set[str]) -> list[ToolName]:
    return [tool for tool in TOOL_ORDER if tool in tools]


def _plan_approval(
    orchestration_id: str,
    policy_profile: str,
    plan: OrchestrationPlan,
) -> OrchestrationApprovalRecord:
    action_id = f"action-{orchestration_id}-orchestration-plan"
    binding_hash = plan.binding_hash()
    return OrchestrationApprovalRecord(
        approval_id=f"approval-{orchestration_id}-orchestration-plan",
        orchestration_id=orchestration_id,
        action_id=action_id,
        arguments_hash=sha256_text(binding_hash),
        policy_profile=policy_profile,
        binding_hash=binding_hash,
    )


def _dependency_order(spec: OrchestrationSpec) -> list[OrchestrationChild]:
    remaining = {child.child_id for child in spec.children}
    completed: set[str] = set()
    ordered: list[OrchestrationChild] = []
    while remaining:
        ready = [
            child
            for child in spec.children
            if child.child_id in remaining and set(child.depends_on).issubset(completed)
        ]
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"orchestration dependency cycle detected: {cycle}")
        child = ready[0]
        ordered.append(child)
        remaining.remove(child.child_id)
        completed.add(child.child_id)
    return ordered


def _write_handoff(
    store: OrchestrationStore,
    policy: PolicyEngine,
    orchestration_id: str,
    upstream: OrchestrationChildRun,
    downstream: OrchestrationChild,
) -> tuple[OrchestrationHandoff, GeneratedHandoffContext]:
    handoff_id = f"{orchestration_id}-{upstream.child_id}-to-{downstream.child_id}"
    artifact_path = (
        store.orchestration_dir
        / "handoffs"
        / (f"{upstream.child_id}-to-{downstream.child_id}.json")
    )
    artifact = store.project_relative(artifact_path)
    summary = _handoff_summary(upstream, downstream)
    content_hash = sha256_text(summary)
    decision = policy.evaluate_generated_context(source=artifact)
    handoff = OrchestrationHandoff(
        handoff_id=handoff_id,
        orchestration_id=orchestration_id,
        from_child_id=upstream.child_id,
        from_run_id=upstream.run_id,
        to_child_id=downstream.child_id,
        artifact=artifact,
        policy_decision_id=decision.decision_id,
        summary=summary,
        content_hash=content_hash,
    )
    store.write_model(f"handoffs/{upstream.child_id}-to-{downstream.child_id}.json", handoff)
    context = GeneratedHandoffContext(
        handoff_id=handoff.handoff_id,
        orchestration_id=orchestration_id,
        upstream_child_id=upstream.child_id,
        upstream_run_id=upstream.run_id,
        source=artifact,
        text=summary,
        content_hash=content_hash,
    )
    return handoff, context


def _handoff_summary(upstream: OrchestrationChildRun, downstream: OrchestrationChild) -> str:
    return "\n".join(
        [
            f"orchestration_handoff: {upstream.child_id} -> {downstream.child_id}",
            f"upstream_child_id: {upstream.child_id}",
            f"upstream_run_id: {upstream.run_id}",
            f"upstream_status: {upstream.status}",
            f"upstream_task_id: {upstream.task_id}",
            f"upstream_summary_artifact: {upstream.run_summary_artifact}",
            f"downstream_child_id: {downstream.child_id}",
            "",
        ]
    )


def _child_record(
    child: OrchestrationChild,
    child_summary: RunSummary,
    materialized_task_path: str,
    handoffs: list[OrchestrationHandoff],
) -> OrchestrationChildRun:
    return OrchestrationChildRun(
        child_id=child.child_id,
        role=child.role,
        title=child.title,
        status=child_summary.status,
        run_id=child_summary.run_id,
        task_id=child_summary.task_id,
        materialized_task_path=materialized_task_path,
        run_summary_artifact=child_summary.artifacts["summary"],
        depends_on=list(child.depends_on),
        handoffs=[
            {
                "handoff_id": handoff.handoff_id,
                "from_child_id": handoff.from_child_id,
                "from_run_id": handoff.from_run_id,
                "artifact": handoff.artifact,
            }
            for handoff in handoffs
            if handoff.to_child_id == child.child_id
        ],
    )


def _aggregate_status(current: OrchestrationStatus, child_status: str) -> OrchestrationStatus:
    if child_status == "failed":
        return "failed"
    if child_status == "paused":
        return "paused"
    if current == "completed" or child_status == "completed":
        return "completed"
    return "dry_run"


def _project_relative_or_name(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _summary_message_for_status(status: str) -> str:
    if status == "dry_run":
        return "orchestration dry run complete"
    if status == "completed":
        return "orchestration complete"
    if status == "paused":
        return "orchestration paused"
    return "orchestration failed"
