from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agent_harness.config import (
    dump_model,
    load_config_with_schema_evidence,
    load_model,
    load_public_model_with_schema_evidence,
)
from agent_harness.context.builder import SkillContextGuidance, build_context_manifest
from agent_harness.context.retrieval import (
    DenseRetriever,
    FakeRetriever,
    LexicalRetriever,
    LocalDenseRetriever,
    QdrantLocalRetriever,
    QdrantServerRetriever,
    Retriever,
    optional_dense_dependencies_available,
)
from agent_harness.core.models import DeterministicMockModel
from agent_harness.model.adapters import ProviderEnvelopeValidationError, ProviderGateway
from agent_harness.model.profiles import (
    ProviderProfileValidationError,
    validate_provider_profile_for_use,
)
from agent_harness.policy import PolicyEngine, load_policy, load_policy_with_schema_evidence
from agent_harness.provider_input import build_provider_input_manifest
from agent_harness.retrieval_indexes import load_index
from agent_harness.schemas import (
    AppliedTemplateRecord,
    ApprovalRecord,
    Checkpoint,
    ContextManifest,
    GitCommitPlan,
    HarnessConfig,
    PolicyProfile,
    ProviderCallAudit,
    ProviderCallAuditManifest,
    ProviderInputManifest,
    ProviderProfileConfig,
    ProviderUseApprovalBinding,
    RetrievalBackendManifest,
    RetrievalIndexManifest,
    RunProviderRecord,
    RunStatus,
    RunSummary,
    RuntimeAdapterRecord,
    Sensitivity,
    SkillResolutionReport,
    TaskSpec,
    TemplateApplyRecord,
    TemplateProposedWrite,
    TemplateSkillRecommendationRecord,
    ToolCall,
    ToolObservation,
    WorkspaceMetadata,
)
from agent_harness.security import collect_advisory_reports, scan_task_security
from agent_harness.skills import (
    build_skill_manifest,
    load_skill_detail,
    render_skill,
    resolve_task_skills,
)
from agent_harness.storage import RunStore, make_event
from agent_harness.templates import load_template, plan_template_apply
from agent_harness.templates.apply import (
    build_template_application_evidence,
    resolve_template_parameters,
)
from agent_harness.tools.executor import ToolExecutor
from agent_harness.tools.git_commit import (
    bind_committed_hash,
    execute_git_commit,
    plan_git_commit,
    validate_git_commit_approval,
)
from agent_harness.utils import (
    hash_file,
    new_run_id,
    now_utc,
    sha256_json,
    sha256_text,
    stable_id,
    write_json,
)


class HarnessRuntime:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.config, self.config_schema_evidence = load_config_with_schema_evidence(
            self.project_root
        )
        self.artifact_root = self.project_root / self.config.artifact_root

    def run_task(
        self,
        task_path: Path,
        profile_name: str | None = None,
        provider_name: str | None = None,
        deny_provider_input: list[str] | None = None,
        auto_approve: bool = False,
        dry_run: bool = False,
        runtime_adapter: str | None = None,
    ) -> RunSummary:
        task, task_schema_evidence = load_public_model_with_schema_evidence(task_path, TaskSpec)
        if runtime_adapter not in {None, "langgraph"}:
            raise ValueError(f"unsupported runtime adapter: {runtime_adapter}")
        selected_profile = profile_name or task.policy_profile or self.config.default_policy
        profile, policy_schema_evidence = load_policy_with_schema_evidence(
            self.project_root, selected_profile
        )
        policy = PolicyEngine(self.project_root, profile)
        run_id = new_run_id(task.task_id)
        store = RunStore(self.artifact_root, run_id)
        started_at = now_utc()
        store.append_event(make_event(run_id, "run_started", {"task_id": task.task_id}))
        schema_versions = {
            "config": self.config_schema_evidence,
            "task": task_schema_evidence,
            "policy": policy_schema_evidence,
        }
        schema_versions_path = store.write_data("schema_versions.json", schema_versions)
        store.append_event(
            make_event(
                run_id,
                "schema_versions_recorded",
                {"schema_versions": schema_versions},
            )
        )
        runtime_adapter_path: Path | None = None
        if runtime_adapter == "langgraph":
            adapter_record = RuntimeAdapterRecord(
                adapter_id="langgraph",
                run_id=run_id,
                task_id=task.task_id,
            )
            runtime_adapter_path = store.write_model("runtime_adapter.json", adapter_record)
            store.append_event(
                make_event(
                    run_id,
                    "runtime_adapter_selected",
                    {"runtime_adapter": adapter_record.model_dump(mode="json")},
                )
            )
        dump_model(store.run_dir / "task.json", task)
        dump_model(store.run_dir / "policy.json", profile)
        security_report = scan_task_security(self.project_root, run_id, task, policy)
        security_path = store.write_model("security_findings.json", security_report)
        advisory_reports = collect_advisory_reports(self.project_root, self.artifact_root)
        advisory_reports_path = (
            store.write_data("advisory_reports.json", advisory_reports)
            if advisory_reports is not None
            else None
        )
        store.append_event(
            make_event(
                run_id,
                "security_scan_completed",
                {
                    "scanner": security_report.scanner,
                    "findings": len(security_report.findings),
                    "gate": security_report.gate.model_dump(mode="json"),
                },
            )
        )
        if security_report.gate.status == "failed":
            store.append_event(
                make_event(
                    run_id,
                    "security_gate_blocked",
                    {
                        "fail_threshold": security_report.gate.fail_threshold,
                        "blocking_finding_ids": security_report.gate.blocking_finding_ids,
                    },
                )
            )
            artifact_paths = {
                "run_dir": store.run_dir,
                "state": store.db_path,
                "task": store.run_dir / "task.json",
                "policy": store.run_dir / "policy.json",
                "events": store.events_path,
                "schema_versions": schema_versions_path,
                "security_findings": security_path,
                "summary": store.run_dir / "summary.json",
                "artifact_index": store.run_dir / "artifact-index.json",
            }
            if advisory_reports_path is not None:
                artifact_paths["advisory_reports"] = advisory_reports_path
            if runtime_adapter_path is not None:
                artifact_paths["runtime_adapter"] = runtime_adapter_path
            return self._finalize_task_run(
                store,
                task,
                started_at,
                "failed",
                artifact_paths,
                approvals=[],
                message="run blocked by security findings",
            )

        skill_resolution = resolve_task_skills(task_path, self.project_root)
        if skill_resolution.status == "failed":
            raise ValueError("task skill resolution failed")
        skill_guidance = _skill_context_guidance(self.project_root, skill_resolution)

        lexical_retriever, dense_retriever, retrieval = _select_retrieval_backend(
            self.config,
            self.project_root,
            self.artifact_root,
        )
        context = build_context_manifest(
            self.project_root,
            run_id,
            task,
            policy,
            lexical_retriever,
            dense_retriever=dense_retriever,
            retrieval=retrieval,
            skill_guidance=skill_guidance,
        )
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
        for operation, source_path, decision in context.retrieval_decisions:
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {
                        "operation": operation,
                        "path": source_path,
                        "decision": decision.model_dump(mode="json"),
                    },
                )
            )
        for skill_id, source, decision in context.skill_decisions:
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {
                        "operation": "skill_context",
                        "skill_id": skill_id,
                        "source": source,
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
        skill_manifest = build_skill_manifest(
            run_id,
            task.task_id,
            skill_resolution,
            manifest,
        )
        skill_manifest_path = (
            store.write_model("skill_manifest.json", skill_manifest)
            if skill_manifest is not None
            else None
        )
        if skill_manifest is not None:
            store.append_event(
                make_event(
                    run_id,
                    "skill_manifest_created",
                    {
                        "context_manifest_id": manifest.manifest_id,
                        "skills": len(skill_manifest.skills),
                    },
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

        provider = self._resolve_provider(task, provider_name)
        provider_path = None
        provider_input_path = None
        provider_calls_path = None
        denied_provider_input = {
            *task.deny_provider_input_sensitivities,
            *_coerce_provider_input_sensitivities(deny_provider_input or []),
        }
        provider_call_approval_ids: list[str] = []
        if provider is not None:
            provider_config = self._configured_provider(provider.provider_profile_id)
            try:
                validate_provider_profile_for_use(provider_config, profile)
            except ProviderProfileValidationError as exc:
                store.append_event(
                    make_event(
                        run_id,
                        "provider_profile_invalid",
                        {
                            "provider_profile_id": provider.provider_profile_id,
                            "transport": provider.transport,
                            "trust_zone": provider.trust_zone,
                            "network": provider.network,
                            "reason": str(exc),
                        },
                    )
                )
                artifact_paths = {
                    "run_dir": store.run_dir,
                    "state": store.db_path,
                    "task": store.run_dir / "task.json",
                    "policy": store.run_dir / "policy.json",
                    "events": store.events_path,
                    "schema_versions": schema_versions_path,
                    "security_findings": security_path,
                    "context_manifest": store.run_dir / "context_manifest.json",
                    "checkpoint": (
                        store.run_dir / "checkpoints" / f"{checkpoint.checkpoint_id}.json"
                    ),
                    "checkpoint_index": store.run_dir / "checkpoint-index.json",
                    "summary": store.run_dir / "summary.json",
                    "artifact_index": store.run_dir / "artifact-index.json",
                }
                if advisory_reports_path is not None:
                    artifact_paths["advisory_reports"] = advisory_reports_path
                if runtime_adapter_path is not None:
                    artifact_paths["runtime_adapter"] = runtime_adapter_path
                if skill_manifest_path is not None:
                    artifact_paths["skill_manifest"] = skill_manifest_path
                return self._finalize_task_run(
                    store,
                    task,
                    started_at,
                    "failed",
                    artifact_paths,
                    approvals=[],
                    message="provider profile validation failed",
                )
            provider_path = store.write_model("provider.json", provider)
            store.append_event(
                make_event(
                    run_id,
                    "provider_selected",
                    {"provider": provider.model_dump(mode="json")},
                )
            )
            provider_calls_path = store.write_model(
                "provider_calls.json",
                ProviderCallAuditManifest(
                    run_id=run_id,
                    task_id=task.task_id,
                    provider_profile_id=provider.provider_profile_id,
                ),
            )
            provider_input = build_provider_input_manifest(
                run_id,
                task.task_id,
                manifest,
                provider,
                policy,
                denied_sensitivities=denied_provider_input,
            )
            provider_input_manifest = provider_input.manifest
            for decision_path, decision in provider_input.decisions:
                store.append_event(
                    make_event(
                        run_id,
                        "policy_decision",
                        {
                            "operation": "provider_input",
                            "path": decision_path,
                            "decision": decision.model_dump(mode="json"),
                        },
                    )
                )

        approvals: list[str] = []
        status = "dry_run" if dry_run else "completed"
        run_message: str | None = None
        should_execute_model = True
        if provider is not None:
            provider_decision = policy.evaluate_provider_use(provider, checkpoint_hash)
            store.append_event(
                make_event(
                    run_id,
                    "policy_decision",
                    {
                        "operation": "provider_use",
                        "provider_profile_id": provider.provider_profile_id,
                        "decision": provider_decision.model_dump(mode="json"),
                    },
                )
            )
            if not provider_decision.allowed:
                status = "failed"
                should_execute_model = False
            elif provider_decision.approval_required:
                provider_input_hash = _provider_input_hash(provider_input_manifest)
                approval = _provider_approval_record(
                    run_id,
                    provider,
                    checkpoint_hash,
                    policy.profile.name,
                    provider_input_hash=provider_input_hash,
                    policy_decision_id=provider_decision.decision_id,
                    auto_approve=auto_approve,
                    dry_run=dry_run,
                )
                store.write_action(
                    approval.action_id,
                    {
                        "kind": "provider_use",
                        "provider": provider.model_dump(mode="json"),
                        "checkpoint_hash": checkpoint_hash,
                        "policy_profile": policy.profile.name,
                        "provider_input_hash": provider_input_hash,
                        "policy_decision_id": provider_decision.decision_id,
                    },
                )
                store.write_approval(approval)
                approvals.append(approval.action_id)
                store.append_event(
                    make_event(
                        run_id,
                        "approval_recorded",
                        {
                            "approval": approval.model_dump(mode="json"),
                            "operation": "provider_use",
                        },
                    )
                )
                if approval.status != "approved":
                    status = "dry_run" if dry_run else "paused"
                    should_execute_model = False
                else:
                    provider_call_approval_ids.append(approval.action_id)
            pending_provider_input = [
                record.record_id
                for record in provider_input_manifest.records
                if record.policy_action == "approval_required"
            ]
            if pending_provider_input:
                approval = _provider_input_approval_record(
                    run_id,
                    provider,
                    pending_provider_input,
                    checkpoint_hash,
                    policy.profile.name,
                    auto_approve=auto_approve,
                    dry_run=dry_run,
                )
                store.write_action(
                    approval.action_id,
                    {
                        "kind": "provider_input",
                        "provider": provider.model_dump(mode="json"),
                        "record_ids": pending_provider_input,
                        "checkpoint_hash": checkpoint_hash,
                        "policy_profile": policy.profile.name,
                    },
                )
                provider_input_manifest = _bind_provider_input_approval(
                    provider_input_manifest,
                    approval.action_id,
                    approval.status == "approved",
                )
                store.write_approval(approval)
                approvals.append(approval.action_id)
                store.append_event(
                    make_event(
                        run_id,
                        "approval_recorded",
                        {
                            "approval": approval.model_dump(mode="json"),
                            "operation": "provider_input",
                        },
                    )
                )
                if approval.status != "approved":
                    status = "dry_run" if dry_run else "paused"
                    should_execute_model = False
                else:
                    provider_call_approval_ids.append(approval.action_id)
            provider_input_path = store.write_model("provider_input.json", provider_input_manifest)
            store.append_event(
                make_event(
                    run_id,
                    "provider_input_created",
                    {
                        "records": len(provider_input_manifest.records),
                        "provider_profile_id": provider.provider_profile_id,
                    },
                )
            )

        if should_execute_model:
            status, model_approvals = _execute_model_actions(
                self.project_root,
                store,
                task,
                policy,
                manifest,
                checkpoint_hash,
                provider=provider,
                provider_config=(
                    self._configured_provider(provider.provider_profile_id)
                    if provider is not None
                    else None
                ),
                provider_approval_ids=provider_call_approval_ids,
                provider_input_manifest=provider_input_manifest if provider is not None else None,
                auto_approve=auto_approve,
                dry_run=dry_run,
            )
            approvals.extend(model_approvals)
            if status == "failed" and any(
                event["type"] == "provider_envelope_rejected" for event in store.events()
            ):
                run_message = "provider envelope validation failed"

        artifact_paths = {
            "run_dir": store.run_dir,
            "state": store.db_path,
            "task": store.run_dir / "task.json",
            "policy": store.run_dir / "policy.json",
            "events": store.events_path,
            "schema_versions": schema_versions_path,
            "security_findings": security_path,
            "context_manifest": store.run_dir / "context_manifest.json",
            "checkpoint": store.run_dir / "checkpoints" / f"{checkpoint.checkpoint_id}.json",
            "checkpoint_index": store.run_dir / "checkpoint-index.json",
            "summary": store.run_dir / "summary.json",
            "artifact_index": store.run_dir / "artifact-index.json",
        }
        if advisory_reports_path is not None:
            artifact_paths["advisory_reports"] = advisory_reports_path
        if runtime_adapter_path is not None:
            artifact_paths["runtime_adapter"] = runtime_adapter_path
        if skill_manifest_path is not None:
            artifact_paths["skill_manifest"] = skill_manifest_path
        if provider_path is not None:
            artifact_paths["provider"] = provider_path
        if provider_input_path is not None:
            artifact_paths["provider_input"] = provider_input_path
        if provider_calls_path is not None:
            artifact_paths["provider_calls"] = provider_calls_path
            artifact_paths["provider_redacted_prompts"] = (
                store.run_dir / "provider/redacted-prompts"
            )
            artifact_paths["provider_redacted_responses"] = (
                store.run_dir / "provider/redacted-responses"
            )
        return self._finalize_task_run(
            store,
            task,
            started_at,
            status,
            artifact_paths,
            approvals=approvals,
            message=run_message,
        )

    def apply_template(
        self,
        template_name: str,
        destination: Path,
        profile_name: str | None = None,
        force: bool = False,
        parameters: dict[str, str] | None = None,
        diagnostics: list[dict[str, object]] | None = None,
    ) -> RunSummary:
        selected_profile = profile_name or self.config.default_policy
        profile = load_policy(self.project_root, selected_profile)
        policy = PolicyEngine(self.project_root, profile)
        template = load_template(template_name, self.project_root)
        template_parameters = resolve_template_parameters(template, parameters or {})
        template_apply = plan_template_apply(
            template,
            destination,
            policy,
            force=force,
            parameters=template_parameters,
        )

        task_id = f"template-apply:{template.template_id}"
        run_id = new_run_id(task_id)
        store = RunStore(self.artifact_root, run_id)
        started_at = now_utc()
        store.append_event(make_event(run_id, "run_started", {"task_id": task_id}))
        dump_model(store.run_dir / "policy.json", profile)
        store.write_model("template_apply.json", template_apply)
        store.append_event(
            make_event(
                run_id,
                "template_apply_planned",
                {
                    "template_id": template_apply.template_id,
                    "version": template_apply.version,
                    "destination": template_apply.destination,
                    "writes": len(template_apply.proposed_writes),
                },
            )
        )

        checkpoint = Checkpoint(
            checkpoint_id=stable_id(
                "checkpoint",
                run_id,
                template_apply.template_id,
                template_apply.destination,
            ),
            run_id=run_id,
            task_hash=sha256_json(_template_apply_arguments_payload(template_apply)),
            manifest_hash=sha256_json(template_apply.model_dump(mode="json")),
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

        action_id = stable_id(
            "action",
            run_id,
            "template_apply",
            _template_apply_arguments_payload(template_apply),
            checkpoint_hash,
        )
        workspace_metadata_relative = (
            Path(self.config.artifact_root) / "workspace.json"
        ).as_posix()
        template_application_relative = (
            Path(self.config.artifact_root) / "template_applications" / f"{run_id}.json"
        ).as_posix()
        template_application = build_template_application_evidence(
            template,
            destination,
            policy,
            parameters=template_parameters,
            mode="apply",
            status="completed",
            created_files=[write.path for write in template_apply.proposed_writes],
            diagnostics=diagnostics or [],
        )
        artifact_paths = {
            "run_dir": store.run_dir,
            "state": store.db_path,
            "policy": store.run_dir / "policy.json",
            "events": store.events_path,
            "template_apply": store.run_dir / "template_apply.json",
            "checkpoint": store.run_dir / "checkpoints" / f"{checkpoint.checkpoint_id}.json",
            "checkpoint_index": store.run_dir / "checkpoint-index.json",
            "summary": store.run_dir / "summary.json",
            "artifact_index": store.run_dir / "artifact-index.json",
            "workspace_metadata": self.project_root / workspace_metadata_relative,
        }
        action_record = {
            "kind": "template_apply",
            "template": {
                "template_id": template_apply.template_id,
                "version": template_apply.version,
                "title": template_apply.title,
                "description": template_apply.description,
            },
            "destination": template_apply.destination,
            "force": template_apply.force,
            "proposed_writes": [
                write.model_dump(mode="json") for write in template_apply.proposed_writes
            ],
            "checkpoint_hash": checkpoint_hash,
            "policy_profile": policy.profile.name,
            "approval_binding": _template_apply_approval_binding(
                template_apply,
                policy.profile.name,
                checkpoint_hash,
            ),
            "workspace_metadata_path": workspace_metadata_relative,
        }
        store.write_action(action_id, action_record)

        approvals: list[str] = []
        status: RunStatus = "completed"
        message = "template applied to clean destination"
        if _template_apply_requires_approval(
            self.project_root,
            destination,
            template_apply,
            force=force,
        ):
            approval = ApprovalRecord(
                approval_id=stable_id("approval", run_id, action_id),
                run_id=run_id,
                action_id=action_id,
                tool_name="template_apply",
                arguments_hash=sha256_json(_template_apply_arguments_payload(template_apply)),
                policy_profile=policy.profile.name,
                checkpoint_hash=checkpoint_hash,
                proposed_effect_hash=sha256_json(_template_apply_effect_payload(template_apply)),
            )
            store.write_approval(approval)
            approvals = [action_id]
            status = "paused"
            message = "run paused for approval"
            store.append_event(
                make_event(
                    run_id,
                    "approval_recorded",
                    {
                        "approval": approval.model_dump(mode="json"),
                        "operation": "template_apply",
                    },
                )
            )
        else:
            store.append_event(
                make_event(
                    run_id,
                    "template_apply_clean_destination",
                    {
                        "template_id": template_apply.template_id,
                        "destination": template_apply.destination,
                    },
                )
            )
            _apply_template_approval(
                self.project_root,
                store,
                template_apply,
                action_id,
                workspace_metadata_path=workspace_metadata_relative,
                template_application=template_application,
                template_application_path=template_application_relative,
            )
            artifact_paths["template_application"] = (
                self.project_root / template_application_relative
            )

        artifacts = {name: self._project_relative(path) for name, path in artifact_paths.items()}
        store.append_event(make_event(run_id, "run_finished", {"status": status}))
        summary = RunSummary(
            run_id=run_id,
            task_id=task_id,
            status=status,
            events_count=store.event_count(),
            approvals=approvals,
            artifacts=artifacts,
            started_at=started_at,
            message=message,
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

    def propose_git_commit(self, run_id: str, final_message: str) -> RunSummary:
        message = final_message.strip()
        if not message:
            raise ValueError("git_commit requires a non-empty final message")
        store = RunStore.open_existing(self.artifact_root, run_id)
        summary = load_model(store.run_dir / "summary.json", RunSummary)
        if summary.status != "completed":
            raise ValueError("git_commit requires a completed run")
        if _has_pending_approvals(store):
            raise ValueError("git_commit requires all prior approvals to be decided")
        task = load_model(store.run_dir / "task.json", TaskSpec)
        profile = load_model(store.run_dir / "policy.json", PolicyProfile)
        policy = PolicyEngine(self.project_root, profile)
        checkpoint_hash = _latest_checkpoint_hash(store)
        policy_call = ToolCall(
            action_id=stable_id(
                "action",
                run_id,
                "git_commit_policy",
                sha256_text(message),
                checkpoint_hash,
            ),
            tool_name="git_commit",
            arguments={"run_id": run_id, "final_message_hash": sha256_text(message)},
            reason="request git commit approval",
        )
        policy_decision = policy.evaluate_tool_call(policy_call, task, checkpoint_hash)
        store.append_event(
            make_event(
                run_id,
                "policy_decision",
                {
                    "operation": "git_commit",
                    "decision": policy_decision.model_dump(mode="json"),
                },
            )
        )
        if not policy_decision.allowed:
            raise PermissionError(policy_decision.reason)

        plan, approval = plan_git_commit(
            self.project_root,
            store,
            task,
            policy,
            checkpoint_hash,
            message,
        )
        plan_path = store.write_model("git_commit.json", plan)
        store.write_action(
            plan.action_id,
            {
                "kind": "git_commit",
                "git_commit": plan.model_dump(mode="json"),
                "checkpoint_hash": checkpoint_hash,
                "policy_profile": policy.profile.name,
            },
        )
        store.append_event(
            make_event(
                run_id,
                "git_commit_planned",
                {
                    "action_id": plan.action_id,
                    "parent_head": plan.parent_head,
                    "file_set": plan.file_set,
                    "diff_hash": plan.diff_hash,
                    "final_message_hash": plan.final_message_hash,
                },
            )
        )
        store.write_approval(approval)
        store.append_event(
            make_event(
                run_id,
                "approval_recorded",
                {
                    "approval": approval.model_dump(mode="json"),
                    "operation": "git_commit",
                },
            )
        )
        artifacts = {
            **summary.artifacts,
            "git_commit": self._project_relative(plan_path),
        }
        approvals = [*summary.approvals, approval.action_id]
        updated = summary.model_copy(
            update={
                "status": "paused",
                "approvals": approvals,
                "artifacts": artifacts,
                "events_count": store.event_count(),
                "ended_at": now_utc(),
                "message": "run paused for approval",
            }
        )
        store.write_summary(updated)
        _update_artifact_index(project_root=self.project_root, store=store, artifacts=artifacts)
        return updated

    def _project_relative(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()

    def _finalize_task_run(
        self,
        store: RunStore,
        task: TaskSpec,
        started_at: datetime,
        status: str,
        artifact_paths: dict[str, Path],
        approvals: list[str],
        message: str | None = None,
    ) -> RunSummary:
        artifacts = {name: self._project_relative(path) for name, path in artifact_paths.items()}
        store.append_event(make_event(store.run_id, "run_finished", {"status": status}))
        summary = RunSummary(
            run_id=store.run_id,
            task_id=task.task_id,
            status=status,  # type: ignore[arg-type]
            events_count=store.event_count(),
            approvals=approvals,
            artifacts=artifacts,
            started_at=started_at,
            message=message or _summary_message_for_status(status),
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
                "run_id": store.run_id,
                "artifacts": artifacts,
                "artifact_hashes": artifact_hashes,
            },
        )
        return summary

    def _resolve_provider(
        self, task: TaskSpec, provider_name: str | None = None
    ) -> RunProviderRecord | None:
        provider_profile_id = (
            provider_name or task.provider_profile or self.config.default_provider_profile
        )
        if provider_profile_id is None:
            return None
        configured = self._configured_provider(provider_profile_id)
        return RunProviderRecord(
            provider_profile_id=configured.provider_profile_id,
            transport=configured.transport,
            trust_zone=configured.trust_zone,
            model=configured.model,
            endpoint_env=configured.endpoint_env,
            endpoint_identity=f"env:{configured.endpoint_env}",
            network=configured.network,
            requires_approval=configured.requires_approval,
        )

    def _configured_provider(self, provider_profile_id: str) -> ProviderProfileConfig:
        for provider in self.config.provider_profiles:
            if provider.provider_profile_id == provider_profile_id:
                return provider
        raise ValueError(f"provider profile not found: {provider_profile_id}")


def approve_action(
    project_root: Path,
    run_id: str,
    action_id: str,
    decision: str,
    actor: str,
    reason: str | None = None,
) -> ApprovalRecord:
    if decision not in {"approve", "deny"}:
        raise ValueError("decision must be approve or deny")
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
    if decision != "approve":
        _record_approval_decision(store, updated)
        _finalize_resumed_run(store, "failed")
        return updated

    action_record = store.read_action(action_id)
    profile = load_policy(project_root, updated.policy_profile)
    policy = PolicyEngine(project_root, profile)
    if action_record.get("kind") == "template_apply":
        template_apply = load_model(store.run_dir / "template_apply.json", TemplateApplyRecord)
        _validate_template_apply_approval(
            updated,
            template_apply,
            checkpoint_hash=str(action_record["checkpoint_hash"]),
            run_id=run_id,
            policy_profile=policy.profile.name,
        )
        _record_approval_decision(store, updated)
        _apply_template_approval(
            project_root,
            store,
            template_apply,
            updated.action_id,
            workspace_metadata_path=str(action_record["workspace_metadata_path"]),
        )
        _finalize_resumed_run(store, "completed")
        _refresh_artifact_index(project_root, store)
        return updated

    if action_record.get("kind") == "git_commit":
        plan = load_model(store.run_dir / "git_commit.json", GitCommitPlan)
        action_plan = GitCommitPlan.model_validate_json(json.dumps(action_record["git_commit"]))
        if action_plan.model_dump(mode="json") != plan.model_dump(mode="json"):
            raise ValueError("git commit approval binding does not match repository state")
        validate_git_commit_approval(
            updated,
            plan,
            run_id=run_id,
            policy_profile=policy.profile.name,
        )
        _record_approval_decision(store, updated)
        commit_hash = execute_git_commit(project_root, plan)
        committed = bind_committed_hash(plan, commit_hash)
        store.write_model("git_commit.json", committed)
        action_record["git_commit"] = committed.model_dump(mode="json")
        action_record["commit_hash"] = commit_hash
        store.write_action(action_id, action_record)
        store.append_event(
            make_event(
                run_id,
                "git_commit_created",
                {
                    "action_id": action_id,
                    "commit_hash": commit_hash,
                    "parent_head": plan.parent_head,
                    "file_set": plan.file_set,
                },
            )
        )
        _finalize_resumed_run(store, "completed")
        _refresh_artifact_index(project_root, store)
        return updated

    task = load_model(store.run_dir / "task.json", TaskSpec)
    if action_record.get("kind") == "provider_use":
        provider = RunProviderRecord.model_validate(action_record["provider"])
        _validate_provider_approval(
            updated,
            provider,
            checkpoint_hash=str(action_record["checkpoint_hash"]),
            run_id=run_id,
            policy_profile=policy.profile.name,
            provider_input_hash=_provider_input_hash(
                load_model(store.run_dir / "provider_input.json", ProviderInputManifest)
            ),
            policy_decision_id=str(action_record["policy_decision_id"]),
        )
        _record_approval_decision(store, updated)
        if _has_pending_approvals(store):
            _update_resumed_summary(store, "paused")
            _refresh_artifact_index(project_root, store)
            return updated
        manifest = load_model(store.run_dir / "context_manifest.json", ContextManifest)
        status, new_approvals = _execute_model_actions(
            project_root,
            store,
            task,
            policy,
            manifest,
            checkpoint_hash=str(action_record["checkpoint_hash"]),
            provider=provider,
            provider_config=runtime._configured_provider(provider.provider_profile_id),
            provider_approval_ids=_approved_provider_execution_approval_ids(store),
            provider_input_manifest=load_model(
                store.run_dir / "provider_input.json", ProviderInputManifest
            ),
            auto_approve=False,
            dry_run=False,
        )
        store.append_event(make_event(run_id, "run_finished", {"status": status}))
        _update_resumed_summary(store, status, new_approvals)
        _refresh_artifact_index(project_root, store)
        return updated
    if action_record.get("kind") == "provider_input":
        provider = RunProviderRecord.model_validate(action_record["provider"])
        _validate_provider_input_approval(
            updated,
            provider,
            record_ids=[str(record_id) for record_id in action_record["record_ids"]],
            checkpoint_hash=str(action_record["checkpoint_hash"]),
            run_id=run_id,
            policy_profile=policy.profile.name,
        )
        _record_approval_decision(store, updated)
        provider_input = load_model(store.run_dir / "provider_input.json", ProviderInputManifest)
        store.write_model(
            "provider_input.json",
            _bind_provider_input_approval(provider_input, updated.action_id, True),
        )
        if _has_pending_approvals(store):
            _update_resumed_summary(store, "paused")
            _refresh_artifact_index(project_root, store)
            return updated
        manifest = load_model(store.run_dir / "context_manifest.json", ContextManifest)
        status, new_approvals = _execute_model_actions(
            project_root,
            store,
            task,
            policy,
            manifest,
            checkpoint_hash=str(action_record["checkpoint_hash"]),
            provider=provider,
            provider_config=runtime._configured_provider(provider.provider_profile_id),
            provider_approval_ids=_approved_provider_execution_approval_ids(store),
            provider_input_manifest=load_model(
                store.run_dir / "provider_input.json", ProviderInputManifest
            ),
            auto_approve=False,
            dry_run=False,
        )
        store.append_event(make_event(run_id, "run_finished", {"status": status}))
        _update_resumed_summary(store, status, new_approvals)
        _refresh_artifact_index(project_root, store)
        return updated

    executor = ToolExecutor(project_root, policy)
    call = ToolCall.model_validate_json(json.dumps(action_record["call"]))
    _validate_tool_approval(executor, call, task, updated, run_id, action_record)
    _record_approval_decision(store, updated)
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


def _record_approval_decision(store: RunStore, approval: ApprovalRecord) -> None:
    store.write_approval(approval)
    store.append_event(
        make_event(
            store.run_id,
            "approval_decided",
            {"approval": approval.model_dump(mode="json")},
        )
    )


def _validate_tool_approval(
    executor: ToolExecutor,
    call: ToolCall,
    task: TaskSpec,
    approval: ApprovalRecord,
    run_id: str,
    action_record: dict[str, object],
) -> None:
    try:
        checkpoint_hash = str(action_record["checkpoint_hash"])
        policy_profile = str(action_record["policy_profile"])
        proposed_effect_hash = str(action_record["proposed_effect_hash"])
    except KeyError as exc:
        raise ValueError("approval binding does not match action") from exc
    expected = {
        "run_id": run_id,
        "action_id": call.action_id,
        "tool_name": call.tool_name,
        "arguments_hash": call.arguments_hash(),
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
        "proposed_effect_hash": proposed_effect_hash,
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
        raise ValueError("approval binding does not match action")
    if policy_profile != executor.policy.profile.name:
        raise ValueError("approval binding does not match action")
    if proposed_effect_hash != executor.proposed_effect_hash(call):
        raise ValueError("approval binding does not match action")
    decision = executor.policy.evaluate_tool_call(call, task, checkpoint_hash)
    if not decision.allowed:
        raise ValueError(decision.reason)


def _finalize_resumed_run(store: RunStore, final_status: str) -> None:
    store.append_event(make_event(store.run_id, "run_finished", {"status": final_status}))
    _update_resumed_summary(store, final_status)


def _execute_model_actions(
    project_root: Path,
    store: RunStore,
    task: TaskSpec,
    policy: PolicyEngine,
    manifest: ContextManifest,
    checkpoint_hash: str,
    provider: RunProviderRecord | None = None,
    provider_config: ProviderProfileConfig | None = None,
    provider_approval_ids: list[str] | None = None,
    provider_input_manifest: ProviderInputManifest | None = None,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> tuple[str, list[str]]:
    executor = ToolExecutor(project_root, policy)
    model = DeterministicMockModel()
    observations: list[ToolObservation] = []
    approvals: list[str] = []
    status = "dry_run" if dry_run else "completed"
    gateway = ProviderGateway(project_root) if provider is not None else None
    if provider is not None and provider_config is None:
        raise ValueError("provider config is required for provider-backed execution")

    if gateway is not None:
        assert provider is not None
        assert provider_config is not None
        try:
            initial_actions, provider_call = gateway.initial_actions(
                store.run_id,
                task,
                manifest,
                provider,
                provider_config,
                approval_ids=provider_approval_ids,
                provider_input=provider_input_manifest,
            )
        except ProviderEnvelopeValidationError as exc:
            _record_provider_envelope_rejection(
                store,
                exc,
                task,
                checkpoint_hash,
                provider_approval_ids or [],
                provider_input_manifest,
            )
            return "failed", approvals
        _append_provider_call_audit(
            store,
            provider_call,
            checkpoint_hash=checkpoint_hash,
            provider_input=provider_input_manifest,
            response_actions=initial_actions,
        )
    else:
        initial_actions = model.initial_actions(task, manifest)

    for call in initial_actions:
        store.append_event(
            make_event(
                store.run_id,
                "model_action",
                {"call": call.model_dump(mode="json")},
            )
        )
        observation, decision = executor.execute(
            call, task, checkpoint_hash, run_id=store.run_id, dry_run=False
        )
        observations.append(observation)
        store.append_event(
            make_event(
                store.run_id,
                "policy_decision",
                {"action_id": call.action_id, "decision": decision.model_dump(mode="json")},
            )
        )
        store.append_event(
            make_event(
                store.run_id,
                "tool_observation",
                {"observation": observation.model_dump(mode="json")},
            )
        )

    if gateway is not None:
        assert provider is not None
        assert provider_config is not None
        try:
            next_actions, provider_call = gateway.next_actions(
                store.run_id,
                task,
                manifest,
                observations,
                provider,
                provider_config,
                approval_ids=provider_approval_ids,
                provider_input=provider_input_manifest,
            )
        except ProviderEnvelopeValidationError as exc:
            _record_provider_envelope_rejection(
                store,
                exc,
                task,
                checkpoint_hash,
                provider_approval_ids or [],
                provider_input_manifest,
            )
            return "failed", approvals
        _append_provider_call_audit(
            store,
            provider_call,
            checkpoint_hash=checkpoint_hash,
            provider_input=provider_input_manifest,
            response_actions=next_actions,
        )
    else:
        next_actions = model.next_actions(task, manifest, observations)

    for call in next_actions:
        store.append_event(
            make_event(
                store.run_id,
                "model_action",
                {"call": call.model_dump(mode="json")},
            )
        )
        approval = None
        if call.tool_name == "patch_file":
            proposed_hash = executor.proposed_effect_hash(call)
            approval = ApprovalRecord(
                approval_id=stable_id("approval", store.run_id, call.action_id),
                run_id=store.run_id,
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
            run_id=store.run_id,
            approval=approval if approval and approval.status == "approved" else None,
            dry_run=False,
        )
        store.append_event(
            make_event(
                store.run_id,
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
                    store.run_id,
                    "approval_recorded",
                    {"approval": approval.model_dump(mode="json")},
                )
            )
        store.append_event(
            make_event(
                store.run_id,
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
    return status, approvals


def _provider_approval_record(
    run_id: str,
    provider: RunProviderRecord,
    checkpoint_hash: str,
    policy_profile: str,
    provider_input_hash: str,
    policy_decision_id: str,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> ApprovalRecord:
    provider_payload = provider.model_dump(mode="json")
    action_id = stable_id("action", run_id, "provider_use", provider_payload, checkpoint_hash)
    binding_hash = sha256_json(provider_payload)
    provider_use_binding = ProviderUseApprovalBinding(
        provider_profile_id=provider.provider_profile_id,
        trust_zone=provider.trust_zone,
        model_id=provider.model,
        provider_input_hash=provider_input_hash,
        policy_decision_id=policy_decision_id,
        checkpoint_hash=checkpoint_hash,
    )
    return ApprovalRecord(
        approval_id=stable_id("approval", run_id, action_id),
        run_id=run_id,
        action_id=action_id,
        tool_name="provider_use",
        arguments_hash=binding_hash,
        policy_profile=policy_profile,
        checkpoint_hash=checkpoint_hash,
        proposed_effect_hash=binding_hash,
        status="approved" if auto_approve and not dry_run else "pending",
        decided_at=now_utc() if auto_approve and not dry_run else None,
        actor="auto-approve" if auto_approve and not dry_run else None,
        provider_use_binding=provider_use_binding,
    )


def _template_apply_arguments_payload(template_apply: TemplateApplyRecord) -> dict[str, object]:
    return {
        "template_id": template_apply.template_id,
        "version": template_apply.version,
        "destination": template_apply.destination,
        "force": template_apply.force,
    }


def _template_apply_effect_payload(template_apply: TemplateApplyRecord) -> dict[str, object]:
    return {
        "template_id": template_apply.template_id,
        "version": template_apply.version,
        "destination": template_apply.destination,
        "plan": _template_apply_plan_payload(template_apply),
        "plan_hash": sha256_json(_template_apply_plan_payload(template_apply)),
        "proposed_writes": [
            {
                "path": write.path,
                "before_hash": write.before_hash,
                "after_hash": write.after_hash,
            }
            for write in template_apply.proposed_writes
        ],
    }


def _template_apply_plan_payload(template_apply: TemplateApplyRecord) -> dict[str, object]:
    planned_files = [write.path for write in template_apply.proposed_writes]
    empty_hash = sha256_text("")
    operation_types = {
        write.path: "create" if write.before_hash == empty_hash else "overwrite"
        for write in template_apply.proposed_writes
    }
    rendered_hashes = {write.path: write.after_hash for write in template_apply.proposed_writes}
    return {
        "template_id": template_apply.template_id,
        "template_version": template_apply.version,
        "target_path": template_apply.destination,
        "planned_files": planned_files,
        "operation_types": operation_types,
        "rendered_hashes": rendered_hashes,
    }


def _template_apply_approval_binding(
    template_apply: TemplateApplyRecord,
    policy_profile: str,
    checkpoint_hash: str,
) -> dict[str, object]:
    plan_payload = _template_apply_plan_payload(template_apply)
    return {
        **plan_payload,
        "plan_hash": sha256_json(plan_payload),
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
    }


def _template_parameter_defaults(parameters: dict[str, dict[str, Any]]) -> dict[str, str]:
    defaults: dict[str, str] = {}
    for name, metadata in parameters.items():
        default = metadata.get("default")
        if default is not None:
            defaults[name] = str(default)
    return defaults


def _template_apply_requires_approval(
    project_root: Path,
    destination: Path,
    template_apply: TemplateApplyRecord,
    *,
    force: bool,
) -> bool:
    if force:
        return True
    if destination.exists():
        if not destination.is_dir():
            return True
        if any(destination.iterdir()):
            return True
    return any((project_root / write.path).exists() for write in template_apply.proposed_writes)


def _validate_template_apply_approval(
    approval: ApprovalRecord,
    template_apply: TemplateApplyRecord,
    checkpoint_hash: str,
    run_id: str,
    policy_profile: str,
) -> None:
    arguments_payload = _template_apply_arguments_payload(template_apply)
    effect_payload = _template_apply_effect_payload(template_apply)
    expected_action_id = stable_id(
        "action",
        run_id,
        "template_apply",
        arguments_payload,
        checkpoint_hash,
    )
    expected = {
        "run_id": run_id,
        "action_id": expected_action_id,
        "tool_name": "template_apply",
        "arguments_hash": sha256_json(arguments_payload),
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
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
        raise ValueError("template-apply approval binding does not match proposed writes")


def _apply_template_approval(
    project_root: Path,
    store: RunStore,
    template_apply: TemplateApplyRecord,
    action_id: str,
    workspace_metadata_path: str,
    template_application: dict[str, Any] | None = None,
    template_application_path: str | None = None,
) -> None:
    for write in template_apply.proposed_writes:
        path = project_root / write.path
        current_hash = _template_file_hash(path) if path.exists() else sha256_text("")
        if current_hash != write.before_hash:
            raise ValueError(f"template apply target changed before approval: {write.path}")

    created_writes: list[tuple[Path, TemplateProposedWrite]] = []
    current_write: TemplateProposedWrite | None = None
    try:
        for write in template_apply.proposed_writes:
            current_write = write
            path = project_root / write.path
            existed = path.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(write.proposed_content.encode("utf-8"))
            if not existed:
                created_writes.append((path, write))
            store.append_event(
                make_event(
                    store.run_id,
                    "template_write_applied",
                    {
                        "path": write.path,
                        "template_id": template_apply.template_id,
                        "version": template_apply.version,
                    },
                )
            )
    except Exception as exc:
        rolled_back_files = _rollback_created_template_files(created_writes)
        if template_application is not None and template_application_path is not None:
            failed_application = dict(template_application)
            failed_application.update(
                {
                    "status": "failed",
                    "created_files": [],
                    "rolled_back_files": rolled_back_files,
                    "failure": {
                        "path": current_write.path if current_write is not None else "",
                        "error": str(exc),
                    },
                }
            )
            write_json(project_root / template_application_path, failed_application)
        store.append_event(
            make_event(
                store.run_id,
                "template_apply_failed",
                {
                    "template_id": template_apply.template_id,
                    "version": template_apply.version,
                    "path": current_write.path if current_write is not None else "",
                    "rolled_back_files": rolled_back_files,
                },
            )
        )
        raise

    if template_application is not None and template_application_path is not None:
        template_application = dict(template_application)
        template_application["created_files"] = [write.path for _, write in created_writes]
        write_json(project_root / template_application_path, template_application)
        store.append_event(
            make_event(
                store.run_id,
                "template_application_recorded",
                {
                    "template_id": template_apply.template_id,
                    "version": template_apply.version,
                    "template_application": template_application_path,
                },
            )
        )

    workspace_path = project_root / workspace_metadata_path
    if workspace_path.exists():
        workspace = WorkspaceMetadata.model_validate_json(
            workspace_path.read_text(encoding="utf-8")
        )
    else:
        workspace = WorkspaceMetadata()
    workspace = workspace.model_copy(
        update={
            "applied_templates": [
                *workspace.applied_templates,
                AppliedTemplateRecord(
                    template_id=template_apply.template_id,
                    version=template_apply.version,
                    destination=template_apply.destination,
                    run_id=store.run_id,
                    action_id=action_id,
                    evidence=template_application_path or "",
                ),
            ],
            "skill_recommendations": [
                *workspace.skill_recommendations,
                *[
                    TemplateSkillRecommendationRecord(
                        skill_id=skill_id,
                        template_id=template_apply.template_id,
                        template_version=template_apply.version,
                        destination=template_apply.destination,
                        run_id=store.run_id,
                        action_id=action_id,
                        evidence=template_application_path or "",
                    )
                    for skill_id in template_apply.recommended_skills
                ],
            ],
        }
    )
    dump_model(workspace_path, workspace)
    store.append_event(
        make_event(
            store.run_id,
            "workspace_metadata_updated",
            {
                "template_id": template_apply.template_id,
                "version": template_apply.version,
                "destination": template_apply.destination,
                "workspace_metadata": workspace_metadata_path,
            },
        )
    )


def _rollback_created_template_files(
    created_writes: list[tuple[Path, TemplateProposedWrite]],
) -> list[str]:
    rolled_back: list[str] = []
    for path, write in reversed(created_writes):
        if not path.is_file():
            continue
        if _template_file_hash(path) != write.after_hash:
            continue
        path.unlink()
        rolled_back.append(write.path)
    return list(reversed(rolled_back))


def _template_file_hash(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def _provider_input_approval_record(
    run_id: str,
    provider: RunProviderRecord,
    record_ids: list[str],
    checkpoint_hash: str,
    policy_profile: str,
    auto_approve: bool = False,
    dry_run: bool = False,
) -> ApprovalRecord:
    payload = {
        "provider": provider.model_dump(mode="json"),
        "record_ids": sorted(record_ids),
    }
    action_id = stable_id("action", run_id, "provider_input", payload, checkpoint_hash)
    binding_hash = sha256_json(payload)
    return ApprovalRecord(
        approval_id=stable_id("approval", run_id, action_id),
        run_id=run_id,
        action_id=action_id,
        tool_name="provider_input",
        arguments_hash=binding_hash,
        policy_profile=policy_profile,
        checkpoint_hash=checkpoint_hash,
        proposed_effect_hash=binding_hash,
        status="approved" if auto_approve and not dry_run else "pending",
        decided_at=now_utc() if auto_approve and not dry_run else None,
        actor="auto-approve" if auto_approve and not dry_run else None,
    )


def _validate_provider_approval(
    approval: ApprovalRecord,
    provider: RunProviderRecord,
    checkpoint_hash: str,
    run_id: str,
    policy_profile: str,
    provider_input_hash: str,
    policy_decision_id: str,
) -> None:
    provider_payload = provider.model_dump(mode="json")
    binding_hash = sha256_json(provider_payload)
    expected_action_id = stable_id(
        "action", run_id, "provider_use", provider_payload, checkpoint_hash
    )
    expected_binding = ProviderUseApprovalBinding(
        provider_profile_id=provider.provider_profile_id,
        trust_zone=provider.trust_zone,
        model_id=provider.model,
        provider_input_hash=provider_input_hash,
        policy_decision_id=policy_decision_id,
        checkpoint_hash=checkpoint_hash,
    )
    expected = {
        "run_id": run_id,
        "action_id": expected_action_id,
        "tool_name": "provider_use",
        "arguments_hash": binding_hash,
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
        "proposed_effect_hash": binding_hash,
        "provider_use_binding": expected_binding.model_dump(mode="json"),
    }
    actual = {
        "run_id": approval.run_id,
        "action_id": approval.action_id,
        "tool_name": approval.tool_name,
        "arguments_hash": approval.arguments_hash,
        "policy_profile": approval.policy_profile,
        "checkpoint_hash": approval.checkpoint_hash,
        "proposed_effect_hash": approval.proposed_effect_hash,
        "provider_use_binding": (
            approval.provider_use_binding.model_dump(mode="json")
            if approval.provider_use_binding is not None
            else None
        ),
    }
    if actual != expected:
        raise ValueError("provider-use approval binding does not match provider operation")


def _validate_provider_input_approval(
    approval: ApprovalRecord,
    provider: RunProviderRecord,
    record_ids: list[str],
    checkpoint_hash: str,
    run_id: str,
    policy_profile: str,
) -> None:
    payload = {
        "provider": provider.model_dump(mode="json"),
        "record_ids": sorted(record_ids),
    }
    binding_hash = sha256_json(payload)
    expected_action_id = stable_id("action", run_id, "provider_input", payload, checkpoint_hash)
    expected = {
        "run_id": run_id,
        "action_id": expected_action_id,
        "tool_name": "provider_input",
        "arguments_hash": binding_hash,
        "policy_profile": policy_profile,
        "checkpoint_hash": checkpoint_hash,
        "proposed_effect_hash": binding_hash,
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
        raise ValueError("provider-input approval binding does not match selected records")


def _bind_provider_input_approval(
    manifest: ProviderInputManifest,
    action_id: str,
    approved: bool,
) -> ProviderInputManifest:
    records = []
    for record in manifest.records:
        if record.policy_action != "approval_required":
            records.append(record)
            continue
        records.append(
            record.model_copy(
                update={
                    "approval_id": action_id,
                    "included": approved,
                }
            )
        )
    return manifest.model_copy(update={"records": records})


def _provider_input_hash(manifest: ProviderInputManifest) -> str:
    return sha256_json(manifest.model_dump(mode="json"))


def _record_provider_envelope_rejection(
    store: RunStore,
    error: ProviderEnvelopeValidationError,
    task: TaskSpec,
    checkpoint_hash: str,
    approval_ids: list[str],
    provider_input: ProviderInputManifest | None,
) -> None:
    audit = error.audit.model_copy(
        update={
            "run_id": store.run_id,
            "task_id": task.task_id,
            "approval_ids": list(dict.fromkeys(approval_ids)),
            "prompt_hash": sha256_json(
                provider_input.model_dump(mode="json") if provider_input is not None else {}
            ),
            "redacted_prompt_summary": {
                "kind": "provider_input",
                "records": len(provider_input.records) if provider_input is not None else 0,
                "included_records": (
                    sum(1 for record in provider_input.records if record.included)
                    if provider_input is not None
                    else 0
                ),
            },
        }
    )
    _append_provider_call_audit(
        store,
        audit,
        checkpoint_hash=checkpoint_hash,
        provider_input=provider_input,
        error_kind="provider_envelope_validation_error",
    )
    store.append_event(
        make_event(
            store.run_id,
            "provider_envelope_rejected",
            {
                "schema_version": "provider_action_envelope.v1",
                "phase": audit.phase,
                "provider_profile_id": audit.provider_profile_id,
                "provider_call_audit_id": audit.audit_id,
            },
        )
    )


def _append_provider_call_audit(
    store: RunStore,
    audit: ProviderCallAudit,
    checkpoint_hash: str,
    provider_input: ProviderInputManifest | None,
    response_actions: list[ToolCall] | None = None,
    error_kind: str | None = None,
) -> None:
    enriched = _enrich_provider_call_audit(
        store,
        audit,
        checkpoint_hash,
        provider_input,
        response_actions=response_actions,
        error_kind=error_kind,
    )
    path = store.run_dir / "provider_calls.json"
    if path.exists():
        manifest = load_model(path, ProviderCallAuditManifest)
        updated = manifest.model_copy(update={"calls": [*manifest.calls, enriched]})
    else:
        updated = ProviderCallAuditManifest(
            run_id=enriched.run_id,
            task_id=enriched.task_id,
            provider_profile_id=enriched.provider_profile_id,
            calls=[enriched],
        )
    store.write_model("provider_calls.json", updated)
    store.append_event(
        make_event(
            store.run_id,
            "provider_call_recorded",
            {"provider_call": enriched.model_dump(mode="json")},
        )
    )


def _enrich_provider_call_audit(
    store: RunStore,
    audit: ProviderCallAudit,
    checkpoint_hash: str,
    provider_input: ProviderInputManifest | None,
    *,
    response_actions: list[ToolCall] | None,
    error_kind: str | None,
) -> ProviderCallAudit:
    prompt_artifact = f"provider/redacted-prompts/{audit.audit_id}.json"
    response_artifact = f"provider/redacted-responses/{audit.audit_id}.json"
    provider_input_hash = (
        _provider_input_hash(provider_input) if provider_input is not None else sha256_json({})
    )
    response_payload = _redacted_provider_response_payload(audit, response_actions, error_kind)
    action_envelope_hash = sha256_json(response_payload["envelope"])
    store.write_data(
        prompt_artifact,
        {
            "schema_version": "provider_redacted_prompt.v1",
            "run_id": store.run_id,
            "task_id": audit.task_id,
            "provider_profile_id": audit.provider_profile_id,
            "provider_input_hash": provider_input_hash,
            "records": _redacted_provider_prompt_records(provider_input),
        },
    )
    store.write_data(
        response_artifact,
        {
            "schema_version": "provider_redacted_response.v1",
            "run_id": store.run_id,
            "task_id": audit.task_id,
            "provider_profile_id": audit.provider_profile_id,
            "action_envelope_hash": action_envelope_hash,
            **response_payload,
        },
    )
    return audit.model_copy(
        update={
            "provider_input_hash": provider_input_hash,
            "action_envelope_hash": action_envelope_hash,
            "checkpoint_hash": checkpoint_hash,
            "redacted_prompt_artifact": prompt_artifact,
            "redacted_response_artifact": response_artifact,
        }
    )


def _redacted_provider_prompt_records(
    provider_input: ProviderInputManifest | None,
) -> list[dict[str, object]]:
    if provider_input is None:
        return []
    return [
        {
            "record_id": record.record_id,
            "manifest_item_id": record.manifest_item_id,
            "source_id": record.source_id,
            "chunk_id": record.chunk_id,
            "path": record.path,
            "sensitivity": record.sensitivity,
            "effective_sensitivity": record.effective_sensitivity,
            "policy_action": record.policy_action,
            "included": record.included,
            "untrusted": record.untrusted,
            "redaction_status": record.redaction_status,
            "redactions_applied": record.redactions_applied,
            "approval_id": record.approval_id,
            "policy_decision_id": record.policy_decision_id,
            "content_hash": record.content_hash,
            "text": record.text,
        }
        for record in provider_input.records
        if record.included
    ]


def _redacted_provider_response_payload(
    audit: ProviderCallAudit,
    response_actions: list[ToolCall] | None,
    error_kind: str | None,
) -> dict[str, object]:
    if error_kind is not None:
        return {
            "kind": error_kind,
            "envelope": {
                "schema_version": "provider_action_envelope.v1",
                "kind": error_kind,
            },
        }
    return {
        "kind": "tool_calls",
        "envelope": {
            "schema_version": "provider_action_envelope.v1",
            "kind": "actions",
            "actions": [
                action.model_dump(mode="json")
                for action in (response_actions if response_actions is not None else [])
            ],
            "actions_hash": audit.actions_hash,
        },
    }


def _has_pending_approvals(store: RunStore) -> bool:
    for path in (store.run_dir / "approvals").glob("*.json"):
        approval = ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if approval.status == "pending":
            return True
    return False


def _update_resumed_summary(
    store: RunStore, final_status: str, new_approvals: list[str] | None = None
) -> None:
    previous = load_model(store.run_dir / "summary.json", RunSummary)
    approvals = list(previous.approvals)
    for action_id in new_approvals or []:
        if action_id not in approvals:
            approvals.append(action_id)
    summary = previous.model_copy(
        update={
            "status": final_status,
            "approvals": approvals,
            "events_count": store.event_count(),
            "ended_at": now_utc(),
            "message": _summary_message_for_status(final_status),
        }
    )
    store.write_summary(summary)


def _approved_provider_execution_approval_ids(store: RunStore) -> list[str]:
    action_ids: list[str] = []
    for path in sorted((store.run_dir / "approvals").glob("*.json")):
        approval = ApprovalRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if approval.status == "approved" and approval.tool_name in {
            "provider_use",
            "provider_input",
        }:
            action_ids.append(approval.action_id)
    return action_ids


def _latest_checkpoint_hash(store: RunStore) -> str:
    checkpoint_index = store.read_data("checkpoint-index.json")
    checkpoint_id = checkpoint_index.get("latest")
    if not isinstance(checkpoint_id, str):
        raise ValueError("checkpoint index does not record a latest checkpoint")
    checkpoint = load_model(store.run_dir / "checkpoints" / f"{checkpoint_id}.json", Checkpoint)
    return checkpoint.checkpoint_hash()


def _update_artifact_index(
    project_root: Path,
    store: RunStore,
    artifacts: dict[str, str],
) -> None:
    existing = (
        store.read_data("artifact-index.json")
        if (store.run_dir / "artifact-index.json").exists()
        else {}
    )
    store.write_data(
        "artifact-index.json",
        {
            "run_id": store.run_id,
            "artifacts": {**existing.get("artifacts", {}), **artifacts},
            "artifact_hashes": existing.get("artifact_hashes", {}),
        },
    )
    _refresh_artifact_index(project_root, store)


def _refresh_artifact_index(project_root: Path, store: RunStore) -> None:
    path = store.run_dir / "artifact-index.json"
    if not path.exists():
        return
    artifact_index = store.read_data("artifact-index.json")
    artifacts = artifact_index.get("artifacts")
    if not isinstance(artifacts, dict):
        return
    artifact_hashes = {
        name: hash_file(project_root / relative)
        for name, relative in artifacts.items()
        if isinstance(relative, str)
        and (project_root / relative).is_file()
        and name not in {"artifact_index", "state"}
    }
    store.write_data(
        "artifact-index.json",
        {
            "run_id": store.run_id,
            "artifacts": artifacts,
            "artifact_hashes": artifact_hashes,
        },
    )


def _summary_message_for_status(status: str) -> str:
    if status == "paused":
        return "run paused for approval"
    if status == "dry_run":
        return "dry run complete"
    if status == "failed":
        return "run failed"
    return "run complete"


def _coerce_provider_input_sensitivities(values: list[str]) -> list[Sensitivity]:
    allowed = {
        "public",
        "internal",
        "confidential",
        "restricted",
        "secret",
        "pii",
        "customer",
        "credential",
        "generated",
        "unknown",
    }
    normalized: list[Sensitivity] = []
    for value in values:
        if value not in allowed:
            raise ValueError(f"unknown provider-input sensitivity: {value}")
        normalized.append(value)  # type: ignore[arg-type]
    return normalized


def _skill_context_guidance(
    project_root: Path,
    resolution: SkillResolutionReport,
) -> list[SkillContextGuidance]:
    guidance: list[SkillContextGuidance] = []
    for record in resolution.skills:
        if not record.required or record.resolution_status != "resolved":
            continue
        detail = load_skill_detail(record.skill_id, project_root)
        skill_hash = record.skill_hash or detail.skill_hash
        if skill_hash is None:
            raise ValueError(f"resolved skill is missing a content hash: {record.skill_id}")
        source_type = record.source_type or detail.source_type
        guidance.append(
            SkillContextGuidance(
                skill_id=record.skill_id,
                version=record.version or detail.version,
                source_type=source_type,
                source=record.source or detail.source,
                skill_hash=skill_hash,
                text=render_skill(record.skill_id, project_root),
                context_class=_skill_context_class(source_type),
                allowed_context_classes=detail.allowed_context_classes,
                inclusion_mode="task_required",
            )
        )
    return guidance


def _skill_context_class(source_type: str) -> Sensitivity:
    if source_type == "bundled":
        return "public"
    return "internal"


def _select_retrieval_backend(
    config: HarnessConfig,
    project_root: Path,
    artifact_root: Path,
) -> tuple[Retriever, DenseRetriever | None, RetrievalBackendManifest]:
    configured = config.retrieval
    if configured is not None and configured.index_id is not None:
        manifest = load_index(project_root, config, configured.index_id)
        mode = configured.default_mode
        index_path = project_root / manifest.index_path
        lexical: Retriever = (
            LexicalRetriever(index_path) if mode in {"lexical", "hybrid"} else FakeRetriever()
        )
        dense: DenseRetriever | None = None
        if mode in {"dense", "hybrid"}:
            if manifest.embedding_backend == "deterministic":
                dense = LocalDenseRetriever(
                    index_path,
                    backend=manifest.embedding_backend,
                    model=manifest.embedding_model or "token-set",
                    version=manifest.embedding_model_version or "baseline",
                )
            elif manifest.embedding_backend == "fastembed":
                if not manifest.qdrant_collection:
                    raise ValueError("qdrant index is missing collection evidence")
                cache_dir = (
                    project_root / manifest.embedding_model_cache_path
                    if manifest.embedding_model_cache_path
                    else None
                )
                if manifest.qdrant_endpoint is not None:
                    dense = QdrantServerRetriever(
                        manifest.qdrant_endpoint,
                        manifest.qdrant_collection,
                        model=manifest.embedding_model or "BAAI/bge-small-en-v1.5",
                        version=manifest.embedding_model_version or "unknown",
                        cache_dir=cache_dir,
                    )
                else:
                    if not manifest.qdrant_storage_path:
                        raise ValueError("qdrant-local index is missing storage evidence")
                    dense = QdrantLocalRetriever(
                        project_root / manifest.qdrant_storage_path,
                        manifest.qdrant_collection,
                        model=manifest.embedding_model or "BAAI/bge-small-en-v1.5",
                        version=manifest.embedding_model_version or "unknown",
                        cache_dir=cache_dir,
                    )
            else:
                raise ValueError(
                    "dense and hybrid context retrieval require a deterministic or "
                    "qdrant-local index"
                )
        return lexical, dense, _configured_index_retrieval_backend(manifest, mode)

    index_path = artifact_root / "indexes" / "documents.jsonl"
    requested_backend = _requested_retrieval_backend(config)
    lexical_retriever = LexicalRetriever(index_path)
    index_id = hash_file(index_path) if index_path.exists() else sha256_text("")
    if requested_backend == "qdrant":
        if not optional_dense_dependencies_available():
            return (
                lexical_retriever,
                None,
                RetrievalBackendManifest(
                    requested_backend="qdrant",
                    active_backend="lexical",
                    backend="lexical",
                    index_id=index_id,
                    fallback_status="used",
                    fallback_reason="missing_optional_dependencies",
                    diagnostics=[
                        "qdrant-client and fastembed are unavailable; lexical fallback active"
                    ],
                    remote_embeddings=False,
                ),
            )
        dense = LocalDenseRetriever(index_path)
        metadata = dense.metadata()
        return (
            lexical_retriever,
            dense,
            RetrievalBackendManifest(
                requested_backend="qdrant",
                active_backend="local_dense_fixture",
                backend=metadata.backend,
                embedding_model=metadata.model,
                embedding_model_version=metadata.version,
                index_id=index_id,
                remote_embeddings=False,
            ),
        )
    return (
        lexical_retriever,
        None,
        RetrievalBackendManifest(
            requested_backend="lexical" if requested_backend != "fake" else "fake",
            active_backend="lexical",
            backend="lexical",
            index_id=index_id,
            remote_embeddings=False,
        ),
    )


def _configured_index_retrieval_backend(
    manifest: RetrievalIndexManifest,
    mode: Literal["lexical", "dense", "hybrid"],
) -> RetrievalBackendManifest:
    if mode == "lexical":
        return RetrievalBackendManifest(
            requested_backend="lexical",
            active_backend="lexical",
            backend="lexical",
            index_id=manifest.index_id,
            index_path=manifest.index_path,
            remote_embeddings=False,
        )
    if manifest.embedding_backend == "fastembed":
        is_server = manifest.qdrant_endpoint is not None
        return RetrievalBackendManifest(
            requested_backend=mode,
            active_backend=(
                f"qdrant_{'server' if is_server else 'local'}_"
                f"{'dense' if mode == 'dense' else 'hybrid'}"
            ),
            backend="qdrant-server" if is_server else "qdrant-local",
            embedding_model=manifest.embedding_model,
            embedding_model_version=manifest.embedding_model_version,
            embedding_model_cache_path=manifest.embedding_model_cache_path,
            index_id=manifest.index_id,
            index_path=manifest.index_path,
            qdrant_collection=manifest.qdrant_collection,
            qdrant_storage_path=manifest.qdrant_storage_path,
            qdrant_endpoint=manifest.qdrant_endpoint,
            remote_embeddings=False,
        )
    return RetrievalBackendManifest(
        requested_backend=mode,
        active_backend=("deterministic_dense" if mode == "dense" else "deterministic_hybrid"),
        backend=manifest.embedding_backend or "deterministic",
        embedding_model=manifest.embedding_model,
        embedding_model_version=manifest.embedding_model_version,
        index_id=manifest.index_id,
        index_path=manifest.index_path,
        remote_embeddings=False,
    )


def _requested_retrieval_backend(config: HarnessConfig) -> str:
    if config.retrieval is None:
        return config.retrieval_backend
    if config.retrieval.default_mode in {"dense", "hybrid"}:
        return "qdrant"
    return "lexical"
