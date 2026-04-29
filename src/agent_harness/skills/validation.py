from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from agent_harness import __version__
from agent_harness.config import load_config
from agent_harness.skills.schema import (
    SkillDetail,
    SkillRegistryRecord,
    SkillSpec,
    SkillValidationReport,
)
from agent_harness.utils import sha256_json

_BUNDLED_SKILLS = resources.files("agent_harness").joinpath("bundled_skills")
_SECRET_LIKE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*=|sk-(?:live|test)-|BEGIN .*PRIVATE KEY"
)
_GENERATED_CITATION_PATTERN = re.compile(
    r"\u3010[^\u3011]*\u2020[^\u3011]*\u3011|\[(?:citation needed|todo:?\s*cite)\]",
    re.I,
)
_PRIVATE_UPLOAD_PATTERN = re.compile(
    r"(?i)(?:/mnt/data/|sandbox:/mnt/data|uploaded file|file-[A-Za-z0-9]{8,})"
)
_AUTHORITY_PATTERNS = (
    re.compile(r"\bgrants?\s+tools?\b", re.I),
    re.compile(r"\bapproves?\s+actions?\b", re.I),
    re.compile(r"\b(?:changes?|widens?|overrides?)\s+policy\b", re.I),
    re.compile(r"\balters?\s+provider profiles?\b", re.I),
    re.compile(r"\bexecutes?\s+code\b", re.I),
    re.compile(r"\bmutates?\s+files?\b", re.I),
    re.compile(r"\bintroduces?\s+network calls?\b", re.I),
)
_METADATA_AUTHORITY_PATTERN = re.compile(
    r"\b(?:read_file|search_code|run_tests|patch_file|git_status|git_commit)\b"
    r"|\bapprove(?:s|d)?\b|\bapproval\b|\bprovider profiles?\b|\bpolicy\b"
    r"|\bsensitivity classes?\b|\bmutate(?:s|d)? files?\b|\bwrite(?:s|d)? files?\b"
    r"|\bexecute(?:s|d)? code\b|\bcommands?\b|\bnetwork calls?\b|https?://",
    re.I,
)


def list_skills(project_root: Path | None = None) -> list[SkillRegistryRecord]:
    root = project_root or Path.cwd()
    records = [_bundled_skill_registry_record(skill_id) for skill_id in _iter_bundled_skill_ids()]
    records.extend(_local_skill_records(root))
    _ensure_unique_skill_ids(records)
    return records


def skill_discovery_diagnostics(project_root: Path | None = None) -> list[dict[str, object]]:
    root = project_root or Path.cwd()
    diagnostics: list[dict[str, object]] = []
    config = load_config(root)
    for configured_dir in config.skills.local_dirs:
        local_dir = _resolve_local_skill_dir(root, configured_dir)
        if not local_dir.is_dir():
            diagnostics.append(
                _diagnostic(
                    "missing_skill_directory",
                    f"missing skill directory: {configured_dir}",
                    configured_dir,
                )
            )
    return diagnostics


def load_skill_detail(skill_id: str, project_root: Path | None = None) -> SkillDetail:
    root = project_root or Path.cwd()
    record = _skill_record(skill_id, root)
    report = _validate_skill_record(record, root)
    text = _try_read_skill_record_text(record, root)
    metadata, body = _parse_frontmatter(text, []) if text is not None else (None, "")
    try:
        spec = SkillSpec.model_validate(metadata or {})
    except ValidationError:
        return SkillDetail(
            skill_id=record.skill_id,
            name=_metadata_string(metadata, "name", record.name),
            version=_metadata_string(metadata, "version", record.version),
            description=_metadata_string(metadata, "description", record.description),
            category=_metadata_string(metadata, "category", ""),
            compatible_agent_harness_versions=_metadata_string(
                metadata,
                "compatible_agent_harness_versions",
                "",
            ),
            required_capabilities=_metadata_list(metadata, "required_capabilities"),
            allowed_context_classes=_metadata_list(metadata, "allowed_context_classes"),
            default_policy_profile=_metadata_optional_string(metadata, "default_policy_profile"),
            related_skills=_metadata_list(metadata, "related_skills"),
            output_artifacts=_metadata_list(metadata, "output_artifacts"),
            validation_commands=_metadata_list(metadata, "validation_commands"),
            examples=_metadata_list(metadata, "examples"),
            source_type=record.source_type,
            source=record.source,
            compatibility_status=report.compatibility_status,
            validation_status=report.status,
            skill_hash=report.skill_hash,
            diagnostics=report.diagnostics,
            body_summary=_body_summary(body),
        )
    return SkillDetail(
        skill_id=spec.skill_id,
        name=spec.name,
        version=spec.version,
        description=spec.description,
        category=spec.category,
        compatible_agent_harness_versions=spec.compatible_agent_harness_versions,
        required_capabilities=spec.required_capabilities,
        allowed_context_classes=spec.allowed_context_classes,
        default_policy_profile=spec.default_policy_profile,
        related_skills=spec.related_skills,
        output_artifacts=spec.output_artifacts,
        validation_commands=spec.validation_commands,
        examples=spec.examples,
        source_type=record.source_type,
        source=record.source,
        compatibility_status=report.compatibility_status,
        validation_status=report.status,
        skill_hash=report.skill_hash,
        diagnostics=report.diagnostics,
        body_summary=_body_summary(body),
    )


def render_skill(skill_id: str, project_root: Path | None = None) -> str:
    root = project_root or Path.cwd()
    detail = load_skill_detail(skill_id, root)
    if detail.validation_status != "passed":
        raise ValueError(f"skill validation failed: {skill_id}")
    record = _skill_record(skill_id, root)
    text = _read_skill_record_text(record, root)
    _metadata, body = _parse_frontmatter(text, [])
    return "\n".join(
        [
            f"# Skill: {detail.name}",
            "",
            f"skill_id: {detail.skill_id}",
            f"version: {detail.version}",
            f"source: {detail.source}",
            f"source_type: {detail.source_type}",
            f"compatibility_status: {detail.compatibility_status}",
            f"validation_status: {detail.validation_status}",
            f"skill_hash: {detail.skill_hash}",
            "",
            "---",
            "",
            body.strip(),
            "",
        ]
    )


def validate_skill_pack_path(path: Path) -> dict[str, object]:
    pack_dir = path.resolve()
    skill_paths = sorted(pack_dir.rglob("SKILL.md"))
    skills = [validate_skill_path(skill_path).model_dump(mode="json") for skill_path in skill_paths]
    diagnostics: list[dict[str, object]] = []
    if not pack_dir.is_dir():
        diagnostics.append(
            _diagnostic("missing_skill_pack", "skill pack path must be a directory", str(pack_dir))
        )
    if not skill_paths:
        diagnostics.append(
            _diagnostic(
                "empty_skill_pack",
                "skill pack does not contain SKILL.md files",
                str(pack_dir),
            )
        )
    status = (
        "passed"
        if not diagnostics and all(skill["status"] == "passed" for skill in skills)
        else "failed"
    )
    return {
        "schema_version": "skill_pack_validation.v1",
        "status": status,
        "pack_path": str(pack_dir),
        "skill_count": len(skills),
        "skills": skills,
        "diagnostics": diagnostics,
    }


def validate_skill(
    skill_id: str,
    project_root: Path | None = None,
) -> SkillValidationReport:
    target = Path(skill_id)
    if target.exists():
        return validate_skill_path(target)

    root = project_root or Path.cwd()
    record = _skill_record(skill_id, root)
    return _validate_skill_record(record, root)


def validate_skill_path(path: Path) -> SkillValidationReport:
    skill_path = path.resolve()
    return _validate_skill_file(skill_path, source=str(skill_path), source_type="direct_path")


def _iter_bundled_skill_ids() -> list[str]:
    skill_ids = []
    for child in _BUNDLED_SKILLS.iterdir():
        if child.is_dir() and child.joinpath("SKILL.md").is_file():
            skill_ids.append(child.name)
    return sorted(skill_ids)


def _bundled_skill_registry_record(skill_id: str) -> SkillRegistryRecord:
    source = f"bundled_skills/{skill_id}/SKILL.md"
    text = _read_bundled_skill_text(skill_id)
    metadata, _body = _parse_frontmatter(text, [])
    spec = SkillSpec.model_validate(metadata or {})
    report = _validate_skill_text(text, source=source, source_type="bundled")
    return SkillRegistryRecord(
        skill_id=spec.skill_id,
        version=spec.version,
        name=spec.name,
        description=spec.description,
        source_type="bundled",
        source=source,
        compatibility_status=report.compatibility_status,
        validation_status=report.status,
        diagnostics=report.diagnostics,
    )


def _local_skill_records(project_root: Path) -> list[SkillRegistryRecord]:
    config = load_config(project_root)
    records: list[SkillRegistryRecord] = []
    for configured_dir in config.skills.local_dirs:
        local_dir = _resolve_local_skill_dir(project_root, configured_dir)
        if not local_dir.is_dir():
            continue
        for skill_path in sorted(local_dir.rglob("SKILL.md")):
            source = _display_source(project_root, skill_path)
            report = _validate_skill_file(skill_path, source=source, source_type="local")
            metadata = _local_skill_metadata(skill_path)
            records.append(
                SkillRegistryRecord(
                    skill_id=_metadata_string(metadata, "skill_id", skill_path.parent.name),
                    version=_metadata_string(metadata, "version", ""),
                    name=_metadata_string(metadata, "name", skill_path.parent.name),
                    description=_metadata_string(metadata, "description", ""),
                    source_type="local",
                    source=source,
                    compatibility_status=report.compatibility_status,
                    validation_status=report.status,
                    diagnostics=report.diagnostics,
                )
            )
    return records


def _resolve_local_skill_dir(project_root: Path, configured_dir: str) -> Path:
    if configured_dir.startswith("~"):
        return Path(configured_dir).expanduser().resolve()
    return (project_root / configured_dir).resolve()


def _display_source(project_root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _metadata_string(metadata: dict[str, Any] | None, field: str, fallback: str) -> str:
    if metadata is None:
        return fallback
    value = metadata.get(field)
    return value if isinstance(value, str) else fallback


def _metadata_optional_string(metadata: dict[str, Any] | None, field: str) -> str | None:
    if metadata is None:
        return None
    value = metadata.get(field)
    return value if isinstance(value, str) else None


def _metadata_list(metadata: dict[str, Any] | None, field: str) -> list[str]:
    if metadata is None:
        return []
    value = metadata.get(field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _ensure_unique_skill_ids(records: list[SkillRegistryRecord]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        if record.skill_id in seen:
            duplicates.add(record.skill_id)
        seen.add(record.skill_id)
    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate skill ids discovered: {duplicate_list}")


def _skill_record(skill_id: str, project_root: Path) -> SkillRegistryRecord:
    for record in list_skills(project_root):
        if record.skill_id == skill_id:
            return record
    raise FileNotFoundError(f"skill not found: {skill_id}")


def _validate_skill_record(
    record: SkillRegistryRecord,
    project_root: Path,
) -> SkillValidationReport:
    if record.source_type == "bundled":
        return _validate_skill_text(
            _read_bundled_skill_text(record.skill_id),
            source=record.source,
            source_type="bundled",
        )
    return _validate_skill_file(
        _skill_record_path(record, project_root),
        source=record.source,
        source_type="local",
    )


def _skill_record_path(record: SkillRegistryRecord, project_root: Path) -> Path:
    source_path = Path(record.source)
    if source_path.is_absolute():
        return source_path
    return project_root / source_path


def _read_skill_record_text(record: SkillRegistryRecord, project_root: Path) -> str:
    if record.source_type == "bundled":
        return _read_bundled_skill_text(record.skill_id)
    return _skill_record_path(record, project_root).read_text(encoding="utf-8")


def _try_read_skill_record_text(
    record: SkillRegistryRecord,
    project_root: Path,
) -> str | None:
    try:
        return _read_skill_record_text(record, project_root)
    except UnicodeDecodeError:
        return None


def _read_bundled_skill_text(skill_id: str) -> str:
    skill_path = _BUNDLED_SKILLS.joinpath(skill_id).joinpath("SKILL.md")
    if not skill_path.is_file():
        raise FileNotFoundError(f"skill not found: {skill_id}")
    return skill_path.read_text(encoding="utf-8")


def _validate_skill_file(
    path: Path,
    *,
    source: str,
    source_type: Literal["local", "direct_path"],
) -> SkillValidationReport:
    skill_path = path.resolve()
    try:
        text = skill_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkillValidationReport(
            status="failed",
            source_type=source_type,
            source=source,
            diagnostics=[
                _diagnostic("non_utf8_skill", "SKILL.md must be UTF-8 text", str(skill_path))
            ],
        )
    return _validate_skill_text(text, source=source, source_type=source_type)


def _local_skill_metadata(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    metadata, _body = _parse_frontmatter(text, [])
    return metadata


def _body_summary(body: str) -> str:
    summary = re.sub(r"\s+", " ", body).strip()
    return summary if len(summary) <= 320 else summary[:317].rstrip() + "..."


def _validate_skill_text(
    text: str,
    *,
    source: str,
    source_type: Literal["bundled", "local", "direct_path"],
) -> SkillValidationReport:
    diagnostics: list[dict[str, object]] = []
    metadata, body = _parse_frontmatter(text, diagnostics)
    skill_id = None
    if metadata is not None and isinstance(metadata.get("skill_id"), str):
        skill_id = metadata["skill_id"]
    spec: SkillSpec | None = None
    compatibility_status: Literal["compatible", "incompatible"] = "compatible"
    skill_hash: str | None = None

    if metadata is not None:
        try:
            spec = SkillSpec.model_validate(metadata)
        except ValidationError as exc:
            diagnostics.extend(_pydantic_diagnostics(exc))
        else:
            skill_id = spec.skill_id
            compatibility_status = _compatibility_status(
                spec.compatible_agent_harness_versions,
                diagnostics,
            )
            diagnostics.extend(_metadata_authority_diagnostics(spec))

    if not body.strip():
        diagnostics.append(_diagnostic("missing_body", "skill body must be non-empty", "body"))
    else:
        diagnostics.extend(_content_marker_diagnostics(body))
        diagnostics.extend(_authority_boundary_diagnostics(body))

    if (
        spec is not None
        and body.strip()
        and compatibility_status == "compatible"
        and not diagnostics
    ):
        skill_hash = sha256_json(
            {
                "metadata": spec.model_dump(mode="json"),
                "body": body.replace("\r\n", "\n").strip(),
            }
        )

    return SkillValidationReport(
        status="failed" if diagnostics else "passed",
        skill_id=skill_id,
        source_type=source_type,
        source=source,
        compatibility_status=compatibility_status,
        skill_hash=skill_hash,
        diagnostics=diagnostics,
    )


def _parse_frontmatter(
    text: str,
    diagnostics: list[dict[str, object]],
) -> tuple[dict[str, Any] | None, str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        diagnostics.append(
            _diagnostic("missing_frontmatter", "SKILL.md must start with YAML frontmatter", "1")
        )
        return None, normalized
    end = normalized.find("\n---\n", 4)
    if end == -1:
        diagnostics.append(
            _diagnostic("unterminated_frontmatter", "SKILL.md frontmatter is not closed", "1")
        )
        return None, ""
    metadata_text = normalized[4:end]
    body = normalized[end + len("\n---\n") :]
    return _parse_yaml_subset(metadata_text, diagnostics), body


def _parse_yaml_subset(
    metadata_text: str,
    diagnostics: list[dict[str, object]],
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for line_number, raw_line in enumerate(metadata_text.splitlines(), start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - ") and current_list_key is not None:
            current = data.setdefault(current_list_key, [])
            if not isinstance(current, list):
                diagnostics.append(
                    _diagnostic(
                        "invalid_frontmatter",
                        f"frontmatter field is not a list: {current_list_key}",
                        str(line_number),
                    )
                )
                continue
            current.append(_parse_scalar(raw_line[4:].strip()))
            continue
        current_list_key = None
        if raw_line.startswith((" ", "\t")):
            diagnostics.append(
                _diagnostic(
                    "unsupported_frontmatter_yaml",
                    "only scalar fields and simple string lists are supported",
                    str(line_number),
                )
            )
            continue
        if ":" not in raw_line:
            diagnostics.append(
                _diagnostic(
                    "invalid_frontmatter",
                    "frontmatter lines must use key: value",
                    str(line_number),
                )
            )
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            diagnostics.append(
                _diagnostic(
                    "invalid_frontmatter",
                    "frontmatter key must be non-empty",
                    str(line_number),
                )
            )
            continue
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = _parse_scalar(value)
    return data


def _parse_scalar(value: str) -> str | list[str]:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(item.strip()) for item in inner.split(",")]
    return _strip_quotes(value)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _compatibility_status(
    expression: str,
    diagnostics: list[dict[str, object]],
) -> Literal["compatible", "incompatible"]:
    status: Literal["compatible", "incompatible"] = "compatible"
    for raw_clause in expression.split(","):
        clause = raw_clause.strip()
        match = re.fullmatch(r"(>=|>|<=|<|==)?\s*v?(\d+\.\d+\.\d+)", clause)
        if match is None:
            diagnostics.append(
                _diagnostic(
                    "unsupported_compatibility_expression",
                    "compatible_agent_harness_versions must use comma-separated "
                    "version comparisons",
                    "compatible_agent_harness_versions",
                )
            )
            return "incompatible"
        operator = match.group(1) or "=="
        target = match.group(2)
        comparison = _compare_versions(__version__, target)
        if not _compatibility_clause_matches(operator, comparison):
            status = "incompatible"
    if status == "incompatible":
        diagnostics.append(
            _diagnostic(
                "incompatible_agent_harness_version",
                "skill is not compatible with this Agent Harness version",
                "compatible_agent_harness_versions",
            )
        )
    return status


def _compatibility_clause_matches(operator: str, comparison: int) -> bool:
    if operator == ">=":
        return comparison >= 0
    if operator == ">":
        return comparison > 0
    if operator == "<=":
        return comparison <= 0
    if operator == "<":
        return comparison < 0
    return comparison == 0


def _content_marker_diagnostics(text: str) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    if _SECRET_LIKE_PATTERN.search(text):
        diagnostics.append(
            _diagnostic("secret_like_value", "secret-like skill content is denied", "body")
        )
    if _GENERATED_CITATION_PATTERN.search(text):
        diagnostics.append(
            _diagnostic(
                "generated_citation_marker", "generated citation markers are denied", "body"
            )
        )
    if _PRIVATE_UPLOAD_PATTERN.search(text):
        diagnostics.append(
            _diagnostic(
                "private_uploaded_file_reference",
                "private uploaded-file references are denied",
                "body",
            )
        )
    return diagnostics


def _authority_boundary_diagnostics(text: str) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for pattern in _AUTHORITY_PATTERNS:
        if pattern.search(text):
            diagnostics.append(
                _diagnostic(
                    "authority_boundary_violation",
                    "skills cannot grant authority, execute code, mutate files, or add network use",
                    "body",
                )
            )
    return diagnostics


def _metadata_authority_diagnostics(spec: SkillSpec) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    checked_fields = {
        "required_capabilities": spec.required_capabilities,
        "validation_commands": spec.validation_commands,
        "examples": spec.examples,
    }
    for field, values in checked_fields.items():
        for value in values:
            if _METADATA_AUTHORITY_PATTERN.search(value):
                diagnostics.append(
                    _diagnostic(
                        "authority_declaration",
                        "skill metadata cannot declare tools, approvals, policy changes, "
                        "file mutation, code execution, or network use",
                        field,
                    )
                )
    return diagnostics


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _version_parts(value: str) -> tuple[int, int, int]:
    parts = value.removeprefix("v").split(".")
    parsed = [int(part) for part in parts[:3]]
    while len(parsed) < 3:
        parsed.append(0)
    return (parsed[0], parsed[1], parsed[2])


def _pydantic_diagnostics(exc: ValidationError) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        rule_id = "invalid_skill_metadata"
        if error["type"] == "missing":
            rule_id = "missing_skill_field"
        elif location == "schema_version":
            rule_id = "unsupported_schema_version"
        elif location == "skill_id":
            rule_id = "invalid_skill_id"
        elif location == "version":
            rule_id = "invalid_skill_version"
        elif location == "description":
            rule_id = "empty_skill_description"
        diagnostics.append(_diagnostic(rule_id, str(error["msg"]), location))
    return diagnostics


def _diagnostic(rule_id: str, message: str, location: str) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": message,
        "location": location,
    }
