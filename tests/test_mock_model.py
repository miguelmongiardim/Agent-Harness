from __future__ import annotations

from agent_harness.model import DeterministicMockModel
from agent_harness.schemas import (
    ContextChunk,
    ContextManifest,
    ContextSource,
    TaskSpec,
    ToolObservation,
)


def _task(task_id: str) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": task_id,
            "title": "Task",
            "intent": "Refactor the helper",
            "target_paths": ["sample.py"],
        }
    )


def _manifest(task_id: str) -> ContextManifest:
    return ContextManifest(manifest_id="m1", run_id="r1", task_id=task_id)


def _manifest_with_query(task_id: str, query: str) -> ContextManifest:
    return ContextManifest(
        manifest_id="m1",
        run_id="r1",
        task_id=task_id,
        sources=[
            ContextSource(
                source_id="s1",
                kind="retrieval",
                path="docs/guide.md",
                content_hash="hash",
                policy_decision_id="decision-1",
            )
        ],
        chunks=[
            ContextChunk(
                chunk_id="c1",
                source_id="s1",
                text=f"Relevant symbol: {query}",
                content_hash="hash",
                start_line=1,
                end_line=1,
            )
        ],
    )


def _read_observation(content: str) -> ToolObservation:
    return ToolObservation(
        action_id="read",
        tool_name="read_file",
        success=True,
        status="ok",
        output={"path": "sample.py", "content": content},
    )


def test_mock_model_does_not_depend_on_task_id_only() -> None:
    model = DeterministicMockModel()
    add_content = "def add_numbers(a, b):\n    return a + b\n"
    multiply_content = "def multiply_numbers(a, b):\n    return a * b\n"

    add_actions = model.next_actions(
        _task("same"), _manifest("same"), [_read_observation(add_content)]
    )
    multiply_actions = model.next_actions(
        _task("same"), _manifest("same"), [_read_observation(multiply_content)]
    )
    renamed_task_actions = model.next_actions(
        _task("different"), _manifest("different"), [_read_observation(add_content)]
    )

    assert (
        add_actions[0].arguments["proposed_content"]
        != multiply_actions[0].arguments["proposed_content"]
    )
    assert (
        add_actions[0].arguments["proposed_content"]
        == renamed_task_actions[0].arguments["proposed_content"]
    )


def test_mock_model_initial_actions_change_with_relevant_context() -> None:
    model = DeterministicMockModel()
    task = TaskSpec.model_validate(
        {
            "schema_version": "task.v1",
            "task_id": "same",
            "title": "Task",
            "intent": "Inspect the relevant helper",
            "max_steps": 2,
        }
    )

    add_actions = model.initial_actions(task, _manifest_with_query("same", "add_numbers"))
    multiply_actions = model.initial_actions(
        task, _manifest_with_query("same", "multiply_numbers")
    )

    assert add_actions[0].tool_name == "search_code"
    assert multiply_actions[0].tool_name == "search_code"
    assert add_actions[0].arguments["query"] == "add_numbers"
    assert multiply_actions[0].arguments["query"] == "multiply_numbers"
