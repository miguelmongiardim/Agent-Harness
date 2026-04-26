from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from agent_harness.model.mock import DeterministicMockModel
from agent_harness.schemas import (
    ContextManifest,
    ProviderCallAudit,
    ProviderCallPhase,
    ProviderProfileConfig,
    ProviderTransport,
    RunProviderRecord,
    TaskSpec,
    ToolCall,
    ToolObservation,
)
from agent_harness.utils import sha256_json, stable_id


class _RecordedFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    fixture_id: str
    transport: ProviderTransport
    planner: Literal["deterministic_mock"] = "deterministic_mock"


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
    ) -> tuple[list[ToolCall], ProviderCallAudit]:
        transport = self._transport(provider, provider_config)
        actions = transport.initial_actions(task, manifest)
        return actions, transport.audit(
            run_id,
            task.task_id,
            "initial_actions",
            actions,
            approval_ids or [],
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
    ) -> tuple[list[ToolCall], ProviderCallAudit]:
        transport = self._transport(provider, provider_config)
        actions = transport.next_actions(task, manifest, observations)
        return actions, transport.audit(
            run_id,
            task.task_id,
            "next_actions",
            actions,
            approval_ids or [],
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
        return self.model.initial_actions(task, manifest)

    def next_actions(
        self,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
    ) -> list[ToolCall]:
        return self.model.next_actions(task, manifest, observations)

    def audit(
        self,
        run_id: str,
        task_id: str,
        phase: ProviderCallPhase,
        actions: list[ToolCall],
        approval_ids: list[str],
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
    ) -> ProviderCallAudit:
        return _build_provider_audit(
            run_id,
            task_id,
            self.provider,
            phase,
            actions,
            approval_ids,
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
    ) -> ProviderCallAudit:
        return _build_provider_audit(
            run_id,
            task_id,
            self.provider,
            phase,
            actions,
            approval_ids,
            mode="recorded_fixture",
            fixture_id=self.fixture.fixture_id,
        )

    def _load_fixture(self) -> _RecordedFixture:
        if not self._endpoint.startswith("recorded://"):
            if os.environ.get("AGENT_HARNESS_ENABLE_LIVE_PROVIDER_TESTS") == "1":
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
    mode: Literal["mock", "recorded_fixture", "live_smoke"],
    fixture_id: str | None = None,
) -> ProviderCallAudit:
    payload = [action.model_dump(mode="json") for action in actions]
    unique_approval_ids = list(dict.fromkeys(approval_ids))
    return ProviderCallAudit(
        audit_id=stable_id(
            "provider-call",
            run_id,
            provider.provider_profile_id,
            phase,
            payload,
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
        actions_hash=sha256_json(payload),
    )
