from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent_harness.model.mock import DeterministicMockModel
from agent_harness.schemas import (
    ContextManifest,
    ProviderActionEnvelope,
    ProviderCallAudit,
    ProviderCallPhase,
    ProviderInputManifest,
    ProviderProfileConfig,
    ProviderTransport,
    RunProviderRecord,
    TaskSpec,
    ToolCall,
    ToolObservation,
)
from agent_harness.tools.patch_file import PatchFileArgs
from agent_harness.tools.read_file import ReadFileArgs
from agent_harness.tools.run_tests import RunTestsArgs
from agent_harness.tools.search_code import SearchCodeArgs
from agent_harness.utils import sha256_json, stable_id


class _RecordedFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    fixture_id: str
    transport: ProviderTransport
    planner: Literal["deterministic_mock"] = "deterministic_mock"
    responses: dict[ProviderCallPhase, dict[str, Any]] = Field(default_factory=dict)


class ProviderEnvelopeValidationError(ValueError):
    def __init__(self, message: str, audit: ProviderCallAudit) -> None:
        super().__init__(message)
        self.audit = audit


class ProviderGateway:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def initial_actions(
        self,
        run_id: str,
        task: TaskSpec,
        manifest: ContextManifest,
        provider: RunProviderRecord,
        provider_config: ProviderProfileConfig,
        approval_ids: list[str] | None = None,
        provider_input: ProviderInputManifest | None = None,
    ) -> tuple[list[ToolCall], ProviderCallAudit]:
        transport = self._transport(provider, provider_config)
        actions = transport.initial_actions(task, manifest)
        return actions, transport.audit(
            run_id,
            task.task_id,
            "initial_actions",
            actions,
            approval_ids or [],
            provider_input,
        )

    def next_actions(
        self,
        run_id: str,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
        provider: RunProviderRecord,
        provider_config: ProviderProfileConfig,
        approval_ids: list[str] | None = None,
        provider_input: ProviderInputManifest | None = None,
    ) -> tuple[list[ToolCall], ProviderCallAudit]:
        transport = self._transport(provider, provider_config)
        actions = transport.next_actions(task, manifest, observations)
        return actions, transport.audit(
            run_id,
            task.task_id,
            "next_actions",
            actions,
            approval_ids or [],
            provider_input,
        )

    def _transport(
        self,
        provider: RunProviderRecord,
        provider_config: ProviderProfileConfig,
    ) -> _BaseTransport:
        if provider.transport == "mock":
            return _MockTransport(provider, provider_config)
        if provider.transport in {"openai_compatible", "anthropic"}:
            return _RecordedTransport(provider, provider_config, self.project_root)
        raise ValueError(f"unsupported provider transport: {provider.transport}")


class _BaseTransport:
    def __init__(
        self,
        provider: RunProviderRecord,
        provider_config: ProviderProfileConfig,
    ) -> None:
        self.provider = provider
        self.provider_config = provider_config
        self.model = DeterministicMockModel()

    def initial_actions(self, task: TaskSpec, manifest: ContextManifest) -> list[ToolCall]:
        return self._actions_from_envelope(
            "initial_actions",
            self._action_envelope(self.model.initial_actions(task, manifest)),
            task,
            manifest,
        )

    def next_actions(
        self,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
    ) -> list[ToolCall]:
        return self._actions_from_envelope(
            "next_actions",
            self._action_envelope(self.model.next_actions(task, manifest, observations)),
            task,
            manifest,
        )

    def _action_envelope(self, actions: list[ToolCall]) -> dict[str, Any]:
        return {
            "schema_version": "provider_action_envelope.v1",
            "kind": "actions",
            "actions": [action.model_dump(mode="python") for action in actions],
        }

    def _actions_from_envelope(
        self,
        phase: ProviderCallPhase,
        payload: dict[str, Any],
        task: TaskSpec,
        manifest: ContextManifest,
    ) -> list[ToolCall]:
        del task
        del manifest
        try:
            envelope = ProviderActionEnvelope.model_validate(payload)
            if envelope.kind == "refusal":
                raise ValueError("provider refused the requested task")
            if envelope.kind == "unsupported":
                raise ValueError("provider returned an unsupported action envelope")
            for action in envelope.actions:
                _validate_tool_arguments(action)
            return envelope.actions
        except (ValidationError, ValueError) as exc:
            audit = _build_provider_validation_failure_audit(
                self.provider,
                phase,
                payload,
                str(exc),
            )
            raise ProviderEnvelopeValidationError(
                "provider envelope validation failed",
                audit,
            ) from exc

    def audit(
        self,
        run_id: str,
        task_id: str,
        phase: ProviderCallPhase,
        actions: list[ToolCall],
        approval_ids: list[str],
        provider_input: ProviderInputManifest | None,
    ) -> ProviderCallAudit:
        raise NotImplementedError


class _MockTransport(_BaseTransport):
    def audit(
        self,
        run_id: str,
        task_id: str,
        phase: ProviderCallPhase,
        actions: list[ToolCall],
        approval_ids: list[str],
        provider_input: ProviderInputManifest | None,
    ) -> ProviderCallAudit:
        return _build_provider_audit(
            run_id,
            task_id,
            self.provider,
            phase,
            actions,
            approval_ids,
            provider_input,
            mode="mock",
        )


class _RecordedTransport(_BaseTransport):
    def __init__(
        self,
        provider: RunProviderRecord,
        provider_config: ProviderProfileConfig,
        project_root: Path,
    ) -> None:
        super().__init__(provider, provider_config)
        self.project_root = project_root
        self._endpoint = _required_env(provider_config.endpoint_env)
        if provider_config.api_key_env is not None:
            _required_env(provider_config.api_key_env)
        self.fixture = self._load_fixture()

    def audit(
        self,
        run_id: str,
        task_id: str,
        phase: ProviderCallPhase,
        actions: list[ToolCall],
        approval_ids: list[str],
        provider_input: ProviderInputManifest | None,
    ) -> ProviderCallAudit:
        return _build_provider_audit(
            run_id,
            task_id,
            self.provider,
            phase,
            actions,
            approval_ids,
            provider_input,
            mode="recorded_fixture",
            fixture_id=self.fixture.fixture_id,
        )

    def initial_actions(self, task: TaskSpec, manifest: ContextManifest) -> list[ToolCall]:
        return self._actions_from_envelope(
            "initial_actions",
            self.fixture.responses.get(
                "initial_actions",
                self._action_envelope(self.model.initial_actions(task, manifest)),
            ),
            task,
            manifest,
        )

    def next_actions(
        self,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
    ) -> list[ToolCall]:
        return self._actions_from_envelope(
            "next_actions",
            self.fixture.responses.get(
                "next_actions",
                self._action_envelope(self.model.next_actions(task, manifest, observations)),
            ),
            task,
            manifest,
        )

    def _load_fixture(self) -> _RecordedFixture:
        if not self._endpoint.startswith("recorded://"):
            if os.environ.get("AGENT_HARNESS_RUN_LIVE_PROVIDER_TESTS") == "1":
                raise ValueError("live provider smoke is not implemented")
            raise ValueError(
                "live provider transport is disabled; use a recorded:// fixture endpoint"
            )
        fixture_ref = self._endpoint.removeprefix("recorded://")
        transport_name, _, fixture_name = fixture_ref.partition("/")
        if not transport_name or not fixture_name:
            raise ValueError(
                f"recorded provider fixture must look like recorded://{self.provider.transport}/<fixture>"
            )
        if transport_name != self.provider.transport:
            raise ValueError(
                f"recorded fixture transport mismatch: expected {self.provider.transport}"
            )
        fixture_path = (
            Path(__file__).resolve().parents[2]
            / "provider_fixtures"
            / transport_name
            / f"{fixture_name}.json"
        )
        if not fixture_path.exists():
            raise ValueError(f"provider fixture not found: {transport_name}/{fixture_name}")
        return _RecordedFixture.model_validate(json.loads(fixture_path.read_text(encoding="utf-8")))


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise ValueError(f"missing required env var: {name}")
    return value


def _build_provider_audit(
    run_id: str,
    task_id: str,
    provider: RunProviderRecord,
    phase: ProviderCallPhase,
    actions: list[ToolCall],
    approval_ids: list[str],
    provider_input: ProviderInputManifest | None,
    mode: Literal["mock", "recorded_fixture", "live_smoke"],
    fixture_id: str | None = None,
) -> ProviderCallAudit:
    response_payload = [action.model_dump(mode="json") for action in actions]
    prompt_payload = _provider_prompt_payload(provider_input)
    unique_approval_ids = list(dict.fromkeys(approval_ids))
    return ProviderCallAudit(
        audit_id=stable_id(
            "provider-call",
            run_id,
            provider.provider_profile_id,
            phase,
            response_payload,
            unique_approval_ids,
            fixture_id,
            mode,
        ),
        run_id=run_id,
        task_id=task_id,
        provider_profile_id=provider.provider_profile_id,
        transport=provider.transport,
        trust_zone=provider.trust_zone,
        model=provider.model,
        endpoint_identity=provider.endpoint_identity,
        network=provider.network,
        phase=phase,
        mode=mode,
        fixture_id=fixture_id,
        approval_ids=unique_approval_ids,
        action_count=len(actions),
        actions_hash=sha256_json(response_payload),
        prompt_hash=sha256_json(prompt_payload),
        response_hash=sha256_json(response_payload),
        redacted_prompt_summary=_redacted_prompt_summary(provider_input),
        redacted_response_summary={
            "kind": "tool_calls",
            "tool_calls": len(actions),
        },
        latency_ms=0,
        token_metrics={
            "prompt_records": len(provider_input.records) if provider_input is not None else 0,
            "included_prompt_records": (
                sum(1 for record in provider_input.records if record.included)
                if provider_input is not None
                else 0
            ),
            "response_actions": len(actions),
        },
        policy_decision_ids=_policy_decision_ids(provider_input),
    )


def _build_provider_validation_failure_audit(
    provider: RunProviderRecord,
    phase: ProviderCallPhase,
    payload: dict[str, Any],
    reason: str,
) -> ProviderCallAudit:
    sanitized_error = {
        "schema_version": "provider_action_envelope.v1",
        "kind": "provider_envelope_validation_error",
        "reason": reason,
    }
    return ProviderCallAudit(
        audit_id=stable_id(
            "provider-call",
            provider.provider_profile_id,
            phase,
            "provider_envelope_validation_error",
            sha256_json(payload),
        ),
        run_id="",
        task_id="",
        provider_profile_id=provider.provider_profile_id,
        transport=provider.transport,
        trust_zone=provider.trust_zone,
        model=provider.model,
        endpoint_identity=provider.endpoint_identity,
        network=provider.network,
        phase=phase,
        mode="recorded_fixture" if provider.transport != "mock" else "mock",
        approval_ids=[],
        action_count=0,
        actions_hash=sha256_json(sanitized_error),
        prompt_hash=sha256_json({"records": []}),
        response_hash=sha256_json(sanitized_error),
        redacted_prompt_summary={"kind": "provider_input", "records": 0, "included_records": 0},
        redacted_response_summary={
            "kind": "provider_envelope_validation_error",
            "schema_version": "provider_action_envelope.v1",
        },
        latency_ms=0,
        token_metrics={},
        policy_decision_ids=[],
    )


def _validate_tool_arguments(action: ToolCall) -> None:
    if action.tool_name == "read_file":
        ReadFileArgs.model_validate(action.arguments)
        return
    if action.tool_name == "search_code":
        SearchCodeArgs.model_validate(action.arguments)
        return
    if action.tool_name == "run_tests":
        RunTestsArgs.model_validate(action.arguments)
        return
    if action.tool_name == "patch_file":
        PatchFileArgs.model_validate(action.arguments)
        return
    if action.tool_name == "git_status":
        if action.arguments:
            raise ValueError("git_status does not accept arguments")
        return
    if action.tool_name == "git_commit":
        raise ValueError("git_commit is not supported in provider action envelopes")
    raise ValueError(f"unknown provider tool: {action.tool_name}")


def _provider_prompt_payload(provider_input: ProviderInputManifest | None) -> dict[str, object]:
    if provider_input is None:
        return {"records": []}
    return {
        "run_id": provider_input.run_id,
        "task_id": provider_input.task_id,
        "provider_profile_id": provider_input.provider_profile_id,
        "trust_zone": provider_input.trust_zone,
        "records": [
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
                "policy_decision_id": record.policy_decision_id,
                "content_hash": record.content_hash,
            }
            for record in provider_input.records
        ],
    }


def _redacted_prompt_summary(
    provider_input: ProviderInputManifest | None,
) -> dict[str, str | int]:
    if provider_input is None:
        return {"kind": "provider_input", "records": 0, "included_records": 0}
    return {
        "kind": "provider_input",
        "records": len(provider_input.records),
        "included_records": sum(1 for record in provider_input.records if record.included),
    }


def _policy_decision_ids(provider_input: ProviderInputManifest | None) -> list[str]:
    if provider_input is None:
        return []
    return list(
        dict.fromkeys(
            record.policy_decision_id
            for record in provider_input.records
            if record.policy_decision_id
        )
    )
