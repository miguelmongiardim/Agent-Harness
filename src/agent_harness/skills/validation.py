from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from agent_harness import __version__
from agent_harness.schemas import SkillSpec, SkillValidationReport
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


def validate_skill(skill_id: str) -> SkillValidationReport:
    target = Path(skill_id)
    if target.exists():
        return validate_skill_path(target)

    skill_path = _BUNDLED_SKILLS.joinpath(skill_id).joinpath("SKILL.md")
    if not skill_path.is_file():
        raise FileNotFoundError(f"skill not found: {skill_id}")
    source = f"bundled_skills/{skill_id}/SKILL.md"
    try:
        text = skill_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkillValidationReport(
            status="failed",
            skill_id=skill_id,
            source_type="bundled",
            source=source,
            diagnostics=[
                _diagnostic("non_utf8_skill", "SKILL.md must be UTF-8 text", "SKILL.md")
            ],
        )
    return _validate_skill_text(text, source=source, source_type="bundled")


def validate_skill_path(path: Path) -> SkillValidationReport:
    skill_path = path.resolve()
    try:
        text = skill_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return SkillValidationReport(
            status="failed",
            source_type="direct_path",
            source=str(skill_path),
            diagnostics=[
                _diagnostic("non_utf8_skill", "SKILL.md must be UTF-8 text", str(skill_path))
            ],
        )
    return _validate_skill_text(text, source=str(skill_path), source_type="direct_path")


def _validate_skill_text(
    text: str,
    *,
    source: str,
    source_type: Literal["bundled", "direct_path"],
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
