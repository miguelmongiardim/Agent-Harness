from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_harness.tasks.schema import TaskSpec


def test_task_schema_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(
            {
                "schema_version": "task.v1",
                "task_id": "task",
                "title": "Task",
                "intent": "Refactor code",
                "target_paths": ["src/example.py"],
                "unexpected": True,
            }
        )


def test_task_schema_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(
            {
                "schema_version": "task.v1",
                "task_id": "task",
                "title": "Task",
                "intent": "Refactor code",
                "target_paths": ["../secret.py"],
            }
        )
