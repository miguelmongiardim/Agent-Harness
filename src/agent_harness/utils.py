from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any


def now_utc() -> datetime:
    fixed = os.environ.get("AGENT_HARNESS_FIXED_TIME")
    if fixed:
        parsed = datetime.fromisoformat(fixed.replace("Z", "+00:00"))
        return parsed.astimezone(UTC)
    return datetime.now(UTC)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def new_run_id(task_id: str) -> str:
    fixed = os.environ.get("AGENT_HARNESS_FIXED_RUN_ID")
    if fixed:
        return fixed
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    safe_task = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in task_id)[:32]
    return f"run-{stamp}-{safe_task}-{suffix}"


def stable_id(prefix: str, *parts: Any, length: int = 16) -> str:
    digest = sha256_json(parts)[:length]
    return f"{prefix}-{digest}"


def normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute():
        raise ValueError("absolute paths are not allowed")
    if any(part in {"..", ""} for part in path.parts):
        raise ValueError("paths must be normalized relative paths")
    return path.as_posix() if path.parts else "."


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def truncate(value: str, limit: int = 6000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[truncated]"
