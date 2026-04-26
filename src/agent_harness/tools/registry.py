from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def path_mode_for_tool(tool_name: str) -> str | None:
    if tool_name == "read_file":
        return "read"
    if tool_name == "patch_file":
        return "write"
    return None
