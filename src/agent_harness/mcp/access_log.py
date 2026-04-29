from __future__ import annotations

import json
from pathlib import Path

from agent_harness.mcp.schema import McpAccessLogRecord
from agent_harness.utils import now_utc


def append_mcp_access_log(
    artifact_root: Path,
    *,
    request_type: str,
    result: str,
    transport: str = "cli",
    profile: str = "default",
    uri: str | None = None,
    prompt_name: str | None = None,
    run_id: str | None = None,
    artifact_type: str | None = None,
    denial_reason: str | None = None,
    prompt_hash: str | None = None,
) -> None:
    record = McpAccessLogRecord(
        timestamp=now_utc().isoformat(),
        transport=transport,
        request_type=request_type,
        resource_uri=uri,
        prompt_name=prompt_name,
        run_id=run_id,
        artifact_type=artifact_type,
        policy_profile=profile,
        result=result,
        denial_reason=denial_reason,
        prompt_hash=prompt_hash,
    ).model_dump(mode="json")
    path = artifact_root / "mcp" / "access-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
