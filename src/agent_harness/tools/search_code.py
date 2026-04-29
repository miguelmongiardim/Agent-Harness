from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from agent_harness.policy import PolicyEngine
from agent_harness.tools.registry import ToolArgs
from agent_harness.tools.schema import ToolCall, ToolObservation


class SearchCodeArgs(ToolArgs):
    query: str
    include_globs: list[str] = Field(default_factory=lambda: ["*.py"])
    max_results: int = Field(default=20, ge=1, le=200)


def execute_search_code(
    call: ToolCall,
    args: SearchCodeArgs,
    project_root: Path,
    policy: PolicyEngine,
) -> ToolObservation:
    results: list[dict[str, Any]] = []
    ignored = {".git", ".venv", ".agent-harness", "__pycache__"}
    for path in sorted(project_root.rglob("*")):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        rel = path.relative_to(project_root).as_posix()
        if not any(
            path.match(pattern) or rel.endswith(pattern.removeprefix("*"))
            for pattern in args.include_globs
        ):
            continue
        path_decision = policy.evaluate_path(rel, "read", "search_code")
        if not path_decision.allowed:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if args.query.lower() in line.lower():
                preview, redactions = policy.redact_text(line.strip())
                results.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "preview": preview[:200],
                        "redactions": redactions,
                    }
                )
                if len(results) >= args.max_results:
                    return search_observation(call, args.query, results)
    return search_observation(call, args.query, results)


def search_observation(
    call: ToolCall,
    query: str,
    results: list[dict[str, Any]],
) -> ToolObservation:
    return ToolObservation(
        action_id=call.action_id,
        tool_name=call.tool_name,
        success=True,
        status="ok",
        output={"query": query, "results": results},
    )
