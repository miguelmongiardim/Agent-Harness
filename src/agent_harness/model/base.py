from __future__ import annotations

from typing import Protocol

from agent_harness.schemas import ContextManifest, TaskSpec, ToolCall, ToolObservation


class ModelClient(Protocol):
    def initial_actions(self, task: TaskSpec, manifest: ContextManifest) -> list[ToolCall]:
        ...

    def next_actions(
        self,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
    ) -> list[ToolCall]:
        ...
