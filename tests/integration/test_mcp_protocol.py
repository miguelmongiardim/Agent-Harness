from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import AnyUrl

from tests.conftest import seed_project

anyio = pytest.importorskip("anyio")
stdio_module = pytest.importorskip("mcp.client.stdio")
session_module = pytest.importorskip("mcp.client.session")


def test_mcp_stdio_server_exposes_resources_and_prompts_without_tools(
    tmp_path: Path,
) -> None:
    seed_project(tmp_path)

    async def exercise_server() -> None:
        server = stdio_module.StdioServerParameters(
            command=sys.executable,
            args=["-m", "agent_harness", "mcp", "serve"],
            cwd=tmp_path,
        )
        async with (
            stdio_module.stdio_client(server) as (read_stream, write_stream),
            session_module.ClientSession(read_stream, write_stream) as session,
        ):
            initialized = await session.initialize()

            assert initialized.capabilities.resources is not None
            assert initialized.capabilities.prompts is not None
            assert initialized.capabilities.tools is None

            resources = await session.list_resources()
            resource_uris = {str(resource.uri) for resource in resources.resources}
            assert "agent-harness://templates" in resource_uris
            assert "agent-harness://skills" in resource_uris
            assert "agent-harness://policies/default" in resource_uris

            read_result = await session.read_resource(AnyUrl("agent-harness://templates"))
            assert len(read_result.contents) == 1
            assert read_result.contents[0].mimeType == "application/json"
            envelope = json.loads(read_result.contents[0].text)
            assert envelope["schema_version"] == "mcp_resource_envelope.v1"
            assert envelope["resource_type"] == "template_collection"

            prompts = await session.list_prompts()
            prompt_names = {prompt.name for prompt in prompts.prompts}
            assert "agent-harness-run-review" in prompt_names

            prompt = await session.get_prompt(
                "agent-harness-run-review",
                {"run_id": "run-mcp-stdio"},
            )
            assert prompt.messages[0].role == "user"
            assert "Agent Harness run evidence" in prompt.messages[0].content.text

    anyio.run(exercise_server)

    records = [
        json.loads(line)
        for line in (tmp_path / ".agent-harness" / "mcp" / "access-log.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {(record["transport"], record["request_type"]) for record in records} >= {
        ("stdio", "resource_read"),
        ("stdio", "prompt_list"),
        ("stdio", "prompt_get"),
    }
