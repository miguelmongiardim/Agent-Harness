from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from agent_harness.config import load_config
from agent_harness.mcp.access_log import append_mcp_access_log
from agent_harness.utils import sha256_text


class PromptDefinition(TypedDict):
    description: str
    allowed_arguments: set[str]
    topic: str


PROMPT_DEFINITIONS: dict[str, PromptDefinition] = {
    "agent-harness-run-review": {
        "description": "Review run summary, context, and evidence for release risks.",
        "allowed_arguments": {"run_id"},
        "topic": "Agent Harness run evidence",
    },
    "agent-harness-policy-review": {
        "description": "Review policy evidence and permission ceilings.",
        "allowed_arguments": {"profile"},
        "topic": "Agent Harness policy evidence",
    },
    "agent-harness-approval-review": {
        "description": "Review approval evidence for decision traceability.",
        "allowed_arguments": {"run_id"},
        "topic": "Agent Harness approval evidence",
    },
    "agent-harness-context-review": {
        "description": "Review context manifest provenance and filtering.",
        "allowed_arguments": {"run_id"},
        "topic": "Agent Harness context evidence",
    },
    "agent-harness-eval-review": {
        "description": "Review eval evidence and scorecard outcomes.",
        "allowed_arguments": {"run_id"},
        "topic": "Agent Harness eval evidence",
    },
    "agent-harness-template-review": {
        "description": "Review template registry and detail evidence.",
        "allowed_arguments": {"template_id"},
        "topic": "Agent Harness template evidence",
    },
    "agent-harness-skill-review": {
        "description": "Review skill registry and detail evidence.",
        "allowed_arguments": {"skill_id"},
        "topic": "Agent Harness skill evidence",
    },
    "agent-harness-retrieval-review": {
        "description": "Review retrieval scorecard and provenance evidence.",
        "allowed_arguments": {"run_id"},
        "topic": "Agent Harness retrieval evidence",
    },
}


def list_mcp_prompts(project_root: Path | None = None) -> dict[str, Any]:
    prompts = [
        {
            "name": name,
            "description": definition["description"],
            "mime_type": "text/markdown",
            "arguments": sorted(definition["allowed_arguments"]),
        }
        for name, definition in PROMPT_DEFINITIONS.items()
    ]
    payload = {
        "schema_version": "mcp_prompt_list.v1",
        "prompts": prompts,
        "count": len(prompts),
    }
    if project_root is not None:
        append_mcp_access_log(
            _artifact_root(project_root),
            request_type="prompt_list",
            result="allowed",
            artifact_type="prompt_registry",
        )
    return payload


def get_mcp_prompt(
    name: str,
    arguments: dict[str, str] | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    prompt_arguments = dict(arguments or {})
    definition = PROMPT_DEFINITIONS.get(name)
    if definition is None:
        response = _denied_prompt_response(
            name,
            prompt_arguments,
            description=None,
            reason="unknown_prompt",
        )
        _log_prompt_get(project_root, name, response)
        return response
    allowed_arguments = set(definition["allowed_arguments"])
    for argument in sorted(prompt_arguments):
        if argument not in allowed_arguments:
            response = _denied_prompt_response(
                name,
                prompt_arguments,
                description=definition["description"],
                reason="unsupported_argument",
                metadata={"argument": argument},
            )
            _log_prompt_get(project_root, name, response)
            return response
    resources = _resource_references(name, prompt_arguments)
    messages = [
        {
            "role": "user",
            "content": _render_prompt(definition["topic"], resources),
        }
    ]
    prompt_hash = sha256_text(
        json.dumps(
            {
                "name": name,
                "arguments": prompt_arguments,
                "resource_references": resources,
                "messages": messages,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    response = {
        "schema_version": "mcp_prompt_response.v1",
        "name": name,
        "description": definition["description"],
        "mime_type": "text/markdown",
        "arguments": prompt_arguments,
        "resource_references": resources,
        "messages": messages,
        "prompt_hash": prompt_hash,
        "denial_status": "allowed",
        "metadata": {},
    }
    _log_prompt_get(project_root, name, response)
    return response


def _denied_prompt_response(
    name: str,
    arguments: dict[str, str],
    *,
    description: object,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    denial_metadata: dict[str, object] = {"denial_reason": reason}
    denial_metadata.update(metadata or {})
    return {
        "schema_version": "mcp_prompt_response.v1",
        "name": name,
        "description": description,
        "mime_type": "text/markdown",
        "arguments": arguments,
        "resource_references": [],
        "messages": [],
        "prompt_hash": None,
        "denial_status": "denied",
        "metadata": denial_metadata,
    }


def _resource_references(name: str, arguments: dict[str, str]) -> list[str]:
    run_id = arguments.get("run_id")
    if name == "agent-harness-run-review":
        if run_id:
            return [
                f"agent-harness://runs/{run_id}/summary",
                f"agent-harness://runs/{run_id}/context",
                f"agent-harness://runs/{run_id}/events",
                f"agent-harness://runs/{run_id}/provider-evidence",
            ]
        return ["agent-harness://runs"]
    if name == "agent-harness-policy-review":
        return [f"agent-harness://policies/{arguments.get('profile', 'default')}"]
    if name == "agent-harness-approval-review":
        return [f"agent-harness://runs/{run_id}/approvals"] if run_id else ["agent-harness://runs"]
    if name == "agent-harness-context-review":
        return [f"agent-harness://runs/{run_id}/context"] if run_id else ["agent-harness://runs"]
    if name == "agent-harness-eval-review":
        return [f"agent-harness://runs/{run_id}/eval"] if run_id else ["agent-harness://runs"]
    if name == "agent-harness-template-review":
        template_id = arguments.get("template_id")
        return (
            [f"agent-harness://templates/{template_id}"]
            if template_id
            else ["agent-harness://templates"]
        )
    if name == "agent-harness-skill-review":
        skill_id = arguments.get("skill_id")
        return [f"agent-harness://skills/{skill_id}"] if skill_id else ["agent-harness://skills"]
    if name == "agent-harness-retrieval-review":
        if run_id:
            return [f"agent-harness://runs/{run_id}/retrieval-scorecard"]
        return ["agent-harness://runs"]
    raise ValueError(f"unknown MCP prompt: {name}")


def _render_prompt(topic: str, resources: list[str]) -> str:
    resource_lines = "\n".join(f"- {resource}" for resource in resources)
    return (
        f"# {topic}\n\n"
        "Use only the referenced Agent Harness resources. Summarize concrete risks, "
        "missing evidence, and release-review questions.\n\n"
        "## Referenced Resources\n\n"
        f"{resource_lines}\n"
    )


def _log_prompt_get(
    project_root: Path | None,
    name: str,
    response: dict[str, Any],
) -> None:
    if project_root is None:
        return
    metadata = response.get("metadata")
    denial_reason = (
        metadata.get("denial_reason")
        if isinstance(metadata, dict) and isinstance(metadata.get("denial_reason"), str)
        else None
    )
    append_mcp_access_log(
        _artifact_root(project_root),
        request_type="prompt_get",
        prompt_name=name,
        result="denied" if response.get("denial_status") == "denied" else "allowed",
        artifact_type="prompt_response",
        denial_reason=denial_reason,
        prompt_hash=(
            response.get("prompt_hash") if isinstance(response.get("prompt_hash"), str) else None
        ),
    )


def _artifact_root(project_root: Path) -> Path:
    root = project_root.resolve()
    return root / load_config(root).artifact_root
