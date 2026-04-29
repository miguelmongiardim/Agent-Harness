from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

from agent_harness import __version__
from agent_harness.mcp.prompts import get_mcp_prompt, list_mcp_prompts
from agent_harness.mcp.resources import list_mcp_resources, read_mcp_resource


def run_mcp_stdio_server(project_root: Path, profile: str = "default") -> None:
    """Run the optional MCP stdio server.

    The MCP SDK is imported only inside this function so base installs can keep
    using CLI resource and prompt inspection without optional dependencies.
    """
    import anyio

    anyio.run(_serve_stdio, project_root.resolve(), profile)


async def _serve_stdio(project_root: Path, profile: str) -> None:
    mcp_server = import_module("mcp.server")
    mcp_stdio = import_module("mcp.server.stdio")

    server = _build_server(project_root, profile)
    async with mcp_stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=mcp_server.NotificationOptions(
                    prompts_changed=False,
                    resources_changed=False,
                    tools_changed=False,
                )
            ),
        )


def _build_server(project_root: Path, profile: str) -> Any:
    mcp_server = import_module("mcp.server")
    mcp_types = import_module("mcp.types")
    helper_types = import_module("mcp.server.lowlevel.helper_types")

    server = mcp_server.Server(
        "agent-harness",
        version=__version__,
        instructions=(
            "Read-only Agent Harness MCP boundary exposing resources and review "
            "prompts only. Tools, writes, approvals, provider execution, and HTTP "
            "transport are not available."
        ),
    )

    @server.list_resources()  # type: ignore[untyped-decorator]
    async def handle_list_resources() -> list[Any]:
        payload = list_mcp_resources(project_root, profile=profile)
        return [
            mcp_types.Resource(
                uri=resource["uri"],
                name=resource["name"],
                description=resource.get("description"),
                mimeType=resource["mime_type"],
            )
            for resource in payload["resources"]
        ]

    @server.read_resource()  # type: ignore[untyped-decorator]
    async def handle_read_resource(uri: Any) -> list[Any]:
        payload = read_mcp_resource(
            project_root,
            str(uri),
            profile=profile,
            transport="stdio",
        )
        return [
            helper_types.ReadResourceContents(
                content=json.dumps(payload, indent=2),
                mime_type=payload.get("mime_type") or "application/json",
            )
        ]

    @server.list_prompts()  # type: ignore[untyped-decorator]
    async def handle_list_prompts() -> list[Any]:
        payload = list_mcp_prompts(project_root, transport="stdio")
        return [
            mcp_types.Prompt(
                name=prompt["name"],
                description=prompt["description"],
                arguments=[
                    mcp_types.PromptArgument(name=argument, required=False)
                    for argument in prompt["arguments"]
                ],
            )
            for prompt in payload["prompts"]
        ]

    @server.get_prompt()  # type: ignore[untyped-decorator]
    async def handle_get_prompt(name: str, arguments: dict[str, str] | None) -> Any:
        payload = get_mcp_prompt(
            name,
            arguments or {},
            project_root=project_root,
            transport="stdio",
        )
        return mcp_types.GetPromptResult(
            description=(
                payload.get("description") if isinstance(payload.get("description"), str) else None
            ),
            messages=[
                mcp_types.PromptMessage(
                    role=message["role"],
                    content=mcp_types.TextContent(
                        type="text",
                        text=message["content"],
                    ),
                )
                for message in payload["messages"]
            ],
            _meta={
                "schema_version": payload["schema_version"],
                "denial_status": payload["denial_status"],
                "prompt_hash": payload["prompt_hash"],
                "resource_references": payload["resource_references"],
                "arguments": payload["arguments"],
                "metadata": payload["metadata"],
            },
        )

    return server
