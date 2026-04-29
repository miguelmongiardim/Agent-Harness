from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from agent_harness.config import write_default_config
from agent_harness.core.runtime import HarnessRuntime
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.release import RELEASE_EVIDENCE_DIR
from agent_harness.schemas import (
    EvalSpec,
    HarnessConfig,
    PolicyProfile,
    TaskSpec,
)
from agent_harness.templates.apply import render_template, resolve_template_parameters
from agent_harness.templates.registry import list_templates, load_template
from agent_harness.templates.schema import TemplateRegistryRecord
from agent_harness.utils import now_utc, write_json

_BUNDLED_TEMPLATES = resources.files("agent_harness").joinpath("bundled_templates")
_PLACEHOLDER_PATTERN = re.compile(r"{{\s*([^{}]+?)\s*}}")
_SUPPORTED_PLACEHOLDER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TEMPLATE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_REMOTE_SOURCE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
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
_REQUIRED_MANIFEST_FIELDS = (
    "schema_version",
    "template_id",
    "version",
    "title",
    "description",
    "minimum_agent_harness_version",
    "required_capabilities",
    "generated_schema_versions",
    "provider_requirements",
    "policy_requirements",
    "retrieval_assumptions",
    "eval_or_demo_metadata",
    "files",
)


def validate_templates(
    project_root: Path,
    *,
    template_id: str | None = None,
    all_templates: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    if all_templates == (template_id is not None):
        raise ValueError("use either --all or a template id")

    listed = {record.template_id: record for record in list_templates(project_root)}
    selected_ids = sorted(listed) if all_templates else [str(template_id)]
    validation_root = project_root / ".agent-harness" / "template-validation"
    validation_root.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="work-", dir=validation_root))
    results = [
        _validate_template(project_root, work_root, selected_id, selected_id in listed)
        for selected_id in selected_ids
    ]
    report = {
        "schema_version": "template_validation.v1",
        "status": "passed" if all(result["status"] == "passed" for result in results) else "failed",
        "generated_at": now_utc().isoformat(),
        "templates": results,
    }
    if output is not None:
        write_json(output, report)
    if all_templates:
        write_json(project_root / RELEASE_EVIDENCE_DIR / "template-validation.json", report)
    return report


def validate_template_pack_path(pack_path: Path) -> dict[str, Any]:
    pack_dir = pack_path.resolve()
    diagnostics = _validate_template_pack_core(pack_dir)
    template_id = _safe_template_id(pack_dir)
    return {
        "schema_version": "template_pack_validation.v1",
        "status": "failed" if diagnostics else "passed",
        "generated_at": now_utc().isoformat(),
        "pack_path": str(pack_dir),
        "template_id": template_id,
        "diagnostics": diagnostics,
    }


def validate_bundled_template_pack(template_id: str) -> dict[str, Any]:
    pack = _BUNDLED_TEMPLATES.joinpath(template_id)
    with resources.as_file(pack) as pack_path:
        return validate_template_pack_path(pack_path)


def _validate_template(
    project_root: Path,
    work_root: Path,
    template_id: str,
    listed: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "template_id": template_id,
        "listed": listed,
        "shown": False,
        "status": "failed",
        "apply": {},
    }
    if not listed:
        result["message"] = "template is not listed in the bundled registry"
        return result

    try:
        record = _listed_template_record(project_root, template_id)
        result["source_type"] = record.source_type
        if record.source_type == "local_pack":
            pack_report = validate_template_pack_path(
                project_root / Path(record.bundle_path).parent
            )
            result["diagnostics"] = pack_report["diagnostics"]
            if pack_report["status"] != "passed":
                result["message"] = "template pack validation failed"
                return result
        detail = load_template(template_id, project_root)
        rendered_detail = render_template(detail, resolve_template_parameters(detail, {}))
        result["shown"] = detail.template_id == template_id and bool(detail.files)
        if detail.source_type == "bundled_pack":
            pack_report = validate_bundled_template_pack(template_id)
            result["diagnostics"] = pack_report["diagnostics"]
            if pack_report["status"] != "passed":
                result["message"] = "template pack validation failed"
                return result
        sandbox = work_root / template_id
        _reset_validation_sandbox(project_root, sandbox)
        if detail.source_type == "local_pack":
            _copy_local_pack_for_validation(project_root, sandbox, record.bundle_path)
        destination = sandbox / "scaffold"
        summary = HarnessRuntime(sandbox).apply_template(template_id, destination)
        result["apply"] = {
            "run_id": summary.run_id,
            "status": summary.status,
            "approvals": summary.approvals,
            "destination": _project_relative(project_root, destination),
            "artifacts": _rebase_artifacts(project_root, sandbox, summary.artifacts),
        }
        result["status"] = (
            "passed"
            if result["shown"]
            and summary.status == "completed"
            and not summary.approvals
            and all((destination / file.path).exists() for file in rendered_detail.files)
            else "failed"
        )
        result["message"] = "passed" if result["status"] == "passed" else "validation failed"
    except Exception as exc:  # pragma: no cover - surfaced as validation data
        result["message"] = str(exc)
    return result


def _listed_template_record(project_root: Path, template_id: str) -> TemplateRegistryRecord:
    for record in list_templates(project_root):
        if record.template_id == template_id:
            return record
    raise FileNotFoundError(f"template not found: {template_id}")


def _validate_template_pack_core(pack_dir: Path) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    manifest_path = pack_dir / "template.v2.toml"
    if not manifest_path.exists():
        return [_diagnostic("missing_manifest", "template.v2.toml is required", "template.v2.toml")]
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            _diagnostic(
                "non_utf8_manifest", "template.v2.toml must be UTF-8 text", "template.v2.toml"
            )
        ]
    try:
        raw = tomllib.loads(manifest_text)
    except tomllib.TOMLDecodeError as exc:
        return [
            _diagnostic(
                "invalid_manifest_toml",
                f"template.v2.toml is invalid TOML: {exc}",
                "template.v2.toml",
            )
        ]

    diagnostics.extend(_manifest_field_diagnostics(raw))
    diagnostics.extend(_hook_script_diagnostics(raw))

    parameters = raw.get("parameters", {})
    declared_parameters = set(parameters) if isinstance(parameters, dict) else set()
    declared_sources: set[Path] = set()
    files = raw.get("files", [])
    if not isinstance(files, list):
        diagnostics.append(_diagnostic("invalid_files", "files must be a list", "template.v2.toml"))
        files = []

    for index, declared in enumerate(files):
        location = f"files[{index}]"
        if not isinstance(declared, dict):
            diagnostics.append(
                _diagnostic("invalid_file_entry", "file entries must be tables", location)
            )
            continue
        target = declared.get("path")
        source = declared.get("source")
        if not isinstance(target, str):
            diagnostics.append(
                _diagnostic("missing_file_path", "file entry path is required", location)
            )
            continue
        diagnostics.extend(_target_path_diagnostics(target, location))
        diagnostics.extend(
            _placeholder_diagnostics(target, declared_parameters, f"{location}.path")
        )
        if not isinstance(source, str):
            diagnostics.append(
                _diagnostic("missing_file_source", "file entry source is required", location)
            )
            continue
        source_path, source_text = _validate_source_file(pack_dir, source, location, diagnostics)
        if source_path is not None:
            declared_sources.add(source_path)
        if source_text is not None:
            diagnostics.extend(_placeholder_diagnostics(source_text, declared_parameters, source))
            diagnostics.extend(_content_marker_diagnostics(source_text, source))
            diagnostics.extend(_generated_example_diagnostics(target, source_text, source))

    diagnostics.extend(_unlisted_file_diagnostics(pack_dir, declared_sources))
    return diagnostics


def _safe_template_id(pack_dir: Path) -> str | None:
    manifest = pack_dir / "template.v2.toml"
    if not manifest.exists():
        return None
    try:
        raw = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    template_id = raw.get("template_id")
    return template_id if isinstance(template_id, str) else None


def _manifest_field_diagnostics(raw: dict[str, Any]) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for field in _REQUIRED_MANIFEST_FIELDS:
        if raw.get(field) in (None, "", [], {}):
            diagnostics.append(
                _diagnostic("missing_manifest_field", f"manifest field is required: {field}", field)
            )
    if raw.get("schema_version") not in (None, "template.v2"):
        diagnostics.append(
            _diagnostic(
                "invalid_schema_version",
                "template packs must use schema_version template.v2",
                "schema_version",
            )
        )
    template_id = raw.get("template_id")
    if isinstance(template_id, str) and not _TEMPLATE_ID_PATTERN.match(template_id):
        diagnostics.append(
            _diagnostic(
                "invalid_template_id", "template_id must be lowercase kebab-case", "template_id"
            )
        )
    version = raw.get("version")
    if isinstance(version, str) and not _VERSION_PATTERN.match(version):
        diagnostics.append(
            _diagnostic("invalid_template_version", "version must use MAJOR.MINOR.PATCH", "version")
        )
    for field in ("minimum_agent_harness_version", "maximum_agent_harness_version"):
        value = raw.get(field)
        if isinstance(value, str) and not _VERSION_PATTERN.match(value):
            diagnostics.append(
                _diagnostic(
                    "invalid_compatibility_version",
                    f"{field} must be a simple MAJOR.MINOR.PATCH version",
                    field,
                )
            )
    return diagnostics


def _hook_script_diagnostics(raw: dict[str, Any]) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for key in raw:
        lowered = key.lower()
        if lowered in {"hook", "hooks"}:
            diagnostics.append(
                _diagnostic("hook_declaration", "template hooks are not supported", key)
            )
        if lowered in {"script", "scripts"}:
            diagnostics.append(
                _diagnostic("script_declaration", "template scripts are not supported", key)
            )
    return diagnostics


def _target_path_diagnostics(path: str, location: str) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    if _is_absolute_or_drive_prefixed(path):
        diagnostics.append(
            _diagnostic("absolute_path", "generated file paths must be relative", location)
        )
    if _has_traversal(path):
        diagnostics.append(
            _diagnostic("path_traversal", "generated file paths cannot contain ..", location)
        )
    if any(part.startswith(".") for part in _path_parts(path)):
        diagnostics.append(
            _diagnostic("hidden_generated_file", "hidden generated files are denied", location)
        )
    return diagnostics


def _validate_source_file(
    pack_dir: Path,
    source: str,
    location: str,
    diagnostics: list[dict[str, object]],
) -> tuple[Path | None, str | None]:
    if _REMOTE_SOURCE_PATTERN.match(source):
        diagnostics.append(
            _diagnostic("remote_source", "remote template sources are not supported", location)
        )
        return None, None
    if _is_absolute_or_drive_prefixed(source) or _has_traversal(source):
        diagnostics.append(
            _diagnostic(
                "unsafe_source_path", "template source paths must stay inside the pack", location
            )
        )
        return None, None
    source_path = pack_dir / source
    try:
        resolved = source_path.resolve()
        resolved.relative_to(pack_dir.resolve())
    except ValueError:
        diagnostics.append(
            _diagnostic("symlink_escape", "template source escapes the pack", location)
        )
        return None, None
    if not source_path.exists():
        diagnostics.append(
            _diagnostic("missing_source_file", "template source file does not exist", source)
        )
        return resolved, None
    if not source_path.is_file():
        diagnostics.append(
            _diagnostic("invalid_source_file", "template source must be a file", source)
        )
        return resolved, None
    try:
        return resolved, source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        diagnostics.append(
            _diagnostic("non_utf8_source", "template sources must be UTF-8 text", source)
        )
        return resolved, None


def _placeholder_diagnostics(
    text: str,
    declared_parameters: set[str],
    location: str,
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for match in _PLACEHOLDER_PATTERN.finditer(text):
        expression = match.group(1).strip()
        if not _SUPPORTED_PLACEHOLDER_PATTERN.match(expression):
            diagnostics.append(
                _diagnostic(
                    "unsupported_placeholder",
                    "only {{ param_name }} placeholders are supported",
                    location,
                )
            )
            continue
        if expression not in declared_parameters:
            diagnostics.append(
                _diagnostic(
                    "undeclared_placeholder",
                    f"placeholder is not declared as a parameter: {expression}",
                    location,
                )
            )
    return diagnostics


def _content_marker_diagnostics(text: str, location: str) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    if _SECRET_LIKE_PATTERN.search(text):
        diagnostics.append(
            _diagnostic("secret_like_value", "secret-like template content is denied", location)
        )
    if _GENERATED_CITATION_PATTERN.search(text):
        diagnostics.append(
            _diagnostic(
                "generated_citation_marker", "generated citation markers are denied", location
            )
        )
    if _PRIVATE_UPLOAD_PATTERN.search(text):
        diagnostics.append(
            _diagnostic(
                "private_uploaded_file_reference",
                "private uploaded-file references are denied",
                location,
            )
        )
    return diagnostics


def _generated_example_diagnostics(
    target: str, content: str, location: str
) -> list[dict[str, object]]:
    if not target.endswith(".json"):
        return []
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    schema_version = payload.get("schema_version")
    model: type[Any]
    if schema_version == "config.v2":
        model = HarnessConfig
    elif schema_version == "task.v2":
        model = TaskSpec
    elif schema_version == "policy.v2":
        model = PolicyProfile
    elif schema_version == "eval.v1":
        model = EvalSpec
    else:
        return []
    try:
        model.model_validate(payload)
    except Exception as exc:
        return [
            _diagnostic(
                "generated_example_invalid", f"generated example is invalid: {exc}", location
            )
        ]
    return []


def _unlisted_file_diagnostics(
    pack_dir: Path, declared_sources: set[Path]
) -> list[dict[str, object]]:
    files_root = pack_dir / "files"
    if not files_root.exists():
        return []
    diagnostics: list[dict[str, object]] = []
    for path in files_root.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved not in declared_sources:
            diagnostics.append(
                _diagnostic(
                    "unlisted_generated_file",
                    "template source files under files/ must be listed in the manifest",
                    path.relative_to(pack_dir).as_posix(),
                )
            )
    return diagnostics


def _is_absolute_or_drive_prefixed(path: str) -> bool:
    return bool(path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path))


def _has_traversal(path: str) -> bool:
    return ".." in _path_parts(path)


def _path_parts(path: str) -> list[str]:
    return [part for part in re.split(r"[\\/]+", path) if part]


def _diagnostic(rule_id: str, message: str, location: str) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "severity": "error",
        "message": message,
        "location": location,
    }


def _reset_validation_sandbox(project_root: Path, sandbox: Path) -> None:
    resolved_root = (project_root / ".agent-harness" / "template-validation").resolve()
    resolved_sandbox = sandbox.resolve()
    try:
        resolved_sandbox.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("template validation sandbox must stay under .agent-harness") from exc
    if sandbox.exists():
        _remove_tree_with_retries(sandbox)
    sandbox.mkdir(parents=True)
    write_default_config(sandbox, force=True)
    write_json(sandbox / "policies" / "default.json", DEFAULT_POLICY)


def _remove_tree_with_retries(path: Path) -> None:
    for attempt in range(6):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.1)


def _copy_local_pack_for_validation(project_root: Path, sandbox: Path, bundle_path: str) -> None:
    bundle = Path(bundle_path)
    pack_dir = bundle.parent
    local_dir = pack_dir.parent
    source_pack = project_root / pack_dir
    target_pack = sandbox / pack_dir
    if target_pack.exists():
        shutil.rmtree(target_pack)
    shutil.copytree(source_pack, target_pack)
    (sandbox / "agent-harness.yaml").write_text(
        "\n".join(
            [
                "schema_version: config.v2",
                "project_name: template-validation",
                "artifact_root: .agent-harness",
                "default_policy: default",
                "retrieval_backend: lexical",
                "template_catalog: bundled",
                "templates:",
                "  local_dirs:",
                f"    - {local_dir.as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _rebase_artifacts(
    project_root: Path,
    sandbox: Path,
    artifacts: dict[str, str],
) -> dict[str, str]:
    return {
        name: _project_relative(project_root, sandbox / relative)
        for name, relative in artifacts.items()
    }


def _project_relative(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())
