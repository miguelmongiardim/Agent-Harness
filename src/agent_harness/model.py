from __future__ import annotations

import re
from typing import Protocol

from agent_harness.schemas import ContextManifest, TaskSpec, ToolCall, ToolObservation
from agent_harness.utils import sha256_text, stable_id


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


class DeterministicMockModel:
    """A content-driven mock model for evals and demos."""

    def initial_actions(self, task: TaskSpec, manifest: ContextManifest) -> list[ToolCall]:
        actions: list[ToolCall] = []
        for path in task.target_paths:
            actions.append(_call("read_file", {"path": path}, "inspect target file"))
        queries = list(task.context_queries)
        if not queries:
            derived_query = self._context_query(manifest)
            if derived_query is not None:
                queries.append(derived_query)
        for query in queries:
            actions.append(
                _call("search_code", {"query": query, "include_globs": ["*.py"]}, "search code")
            )
        return actions[: task.max_steps]

    def next_actions(
        self,
        task: TaskSpec,
        manifest: ContextManifest,
        observations: list[ToolObservation],
    ) -> list[ToolCall]:
        del manifest
        actions: list[ToolCall] = []
        intent = task.intent.lower()
        if "refactor" not in intent and "rename" not in intent and "type" not in intent:
            return actions
        for observation in observations:
            if observation.tool_name != "read_file" or not observation.success:
                continue
            path = observation.output.get("path")
            content = observation.output.get("content")
            if not isinstance(path, str) or not isinstance(content, str):
                continue
            proposed = self._propose_python_refactor(content)
            if proposed and proposed != content:
                actions.append(
                    _call(
                        "patch_file",
                        {
                            "path": path,
                            "before_hash": sha256_text(content),
                            "proposed_content": proposed,
                        },
                        "apply deterministic python refactor",
                    )
                )
                break
        if actions:
            for command in task.test_commands:
                actions.append(_call("run_tests", {"command": command}, "run allow-listed tests"))
        return actions[: task.max_steps]

    def _propose_python_refactor(self, content: str) -> str | None:
        if "def add_numbers(a, b):" in content:
            return (
                content.replace(
                    "def add_numbers(a, b):\n    return a + b",
                    "def add(a: int, b: int) -> int:\n    return a + b",
                )
                .replace("add_numbers(", "add(")
                .replace("Add two numbers.", "Add two integers.")
            )
        if "def multiply_numbers(a, b):" in content:
            return (
                content.replace(
                    "def multiply_numbers(a, b):\n    return a * b",
                    "def multiply(a: int, b: int) -> int:\n    return a * b",
                )
                .replace("multiply_numbers(", "multiply(")
            )
        if "# TODO: simplify" in content and "return value + 0" in content:
            return content.replace("# TODO: simplify\n    return value + 0", "return value")
        return None

    def _context_query(self, manifest: ContextManifest) -> str | None:
        for chunk in manifest.chunks:
            for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]*", chunk.text):
                token = match.group(0)
                if "_" in token:
                    return token
        return None


def _call(tool_name: str, arguments: dict[str, object], reason: str) -> ToolCall:
    return ToolCall(
        action_id=stable_id("action", tool_name, arguments),
        tool_name=tool_name,  # type: ignore[arg-type]
        arguments=arguments,
        reason=reason,
    )
