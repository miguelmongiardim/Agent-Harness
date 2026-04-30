from __future__ import annotations

import argparse
import importlib.util
import json
import secrets
import sys
from importlib import import_module
from pathlib import Path

from pydantic import ValidationError

from agent_harness.benchmarks import (
    list_benchmark_packs,
    load_benchmark_pack,
    run_benchmark_case,
)
from agent_harness.config import load_config, load_public_model, write_default_config
from agent_harness.context.retrieval import ingest_documents
from agent_harness.core.runtime import HarnessRuntime, approve_action
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.demos import (
    record_python_refactor_demo_if_applicable,
    run_provider_audit_demo,
)
from agent_harness.docs_check import write_docs_check_report
from agent_harness.doctor import doctor
from agent_harness.evals import run_builtin_evals, write_eval_report
from agent_harness.exporters import export_json, export_markdown, export_sarif
from agent_harness.mcp import (
    get_mcp_prompt,
    list_mcp_prompts,
    list_mcp_resources,
    read_mcp_resource,
)
from agent_harness.migration import migrate_schemas
from agent_harness.orchestration import (
    approve_orchestration_plan,
    inspect_orchestration,
    resume_orchestration,
    run_orchestration,
)
from agent_harness.policy import PolicyEngine, load_policy
from agent_harness.release import (
    build_release_package_check_report,
    build_release_readiness_report,
)
from agent_harness.retrieval_indexes import (
    build_retrieval_index,
    delete_index,
    list_indexes,
    load_index,
    manifest_path,
    query_index,
)
from agent_harness.retrieval_scorecards import run_retrieval_scorecard
from agent_harness.skills import (
    list_skills,
    load_skill_detail,
    render_skill,
    resolve_task_skills,
    skill_discovery_diagnostics,
    validate_skill,
    validate_skill_pack_path,
)
from agent_harness.storage import RunStore
from agent_harness.tasks.schema import TaskSpec
from agent_harness.templates import list_templates, load_template
from agent_harness.templates.apply import (
    build_template_application_evidence,
    resolve_template_parameters,
)
from agent_harness.templates.schema import TemplateDetail
from agent_harness.templates.validation import (
    validate_bundled_template_pack,
    validate_template_pack_path,
    validate_templates,
)
from agent_harness.utils import load_json, write_json

STARTER_DOC = """# Agent Harness Project

## Implemented Locally

- Local configuration lives in `agent-harness.yaml`.
- Policy profiles live in `policies/`.
- Run and retrieval artifacts live under `.agent-harness/`.
- The bundled `python-lib` template can scaffold a small Python library.

## Roadmap / Not Enabled By Init

- Network model providers, hosted services, web APIs, web UIs, and production
  assurance features are outside this initialized project scaffold.
- Future capabilities must be added through tested Agent Harness behavior before
  this project documentation describes them as available.
"""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-harness")
    sub = parser.add_subparsers(required=True)

    init = sub.add_parser("init")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    template = sub.add_parser("template")
    template_sub = template.add_subparsers(required=True)
    template_list = template_sub.add_parser("list")
    template_list.set_defaults(func=cmd_template_list)
    template_show = template_sub.add_parser("show")
    template_show.add_argument("name")
    template_show.set_defaults(func=cmd_template_show)
    template_validate = template_sub.add_parser("validate")
    template_validate.add_argument("name", nargs="?")
    template_validate.add_argument("--all", action="store_true")
    template_validate.add_argument("--output")
    template_validate.set_defaults(func=cmd_template_validate)
    template_pack = template_sub.add_parser("pack")
    template_pack_sub = template_pack.add_subparsers(required=True)
    template_pack_validate = template_pack_sub.add_parser("validate")
    template_pack_validate.add_argument("path")
    template_pack_validate.set_defaults(func=cmd_template_pack_validate)
    template_apply = template_sub.add_parser("apply")
    template_apply.add_argument("name")
    template_apply.add_argument("--target")
    template_apply.add_argument("--destination")
    template_apply.add_argument("--force", action="store_true")
    template_apply.add_argument("--profile", default="default")
    template_apply.add_argument("--param", action="append", default=[])
    template_apply_mode = template_apply.add_mutually_exclusive_group()
    template_apply_mode.add_argument("--dry-run", action="store_true")
    template_apply_mode.add_argument("--preview-diff", action="store_true")
    template_apply.set_defaults(func=cmd_template_apply)

    skill = sub.add_parser("skill")
    skill_sub = skill.add_subparsers(required=True)
    skill_list = skill_sub.add_parser("list")
    skill_list.set_defaults(func=cmd_skill_list)
    skill_show = skill_sub.add_parser("show")
    skill_show.add_argument("skill_id")
    skill_show.set_defaults(func=cmd_skill_show)
    skill_render = skill_sub.add_parser("render")
    skill_render.add_argument("skill_id")
    skill_render.set_defaults(func=cmd_skill_render)
    skill_validate = skill_sub.add_parser("validate")
    skill_validate.add_argument("skill_id")
    skill_validate.set_defaults(func=cmd_skill_validate)
    skill_resolve = skill_sub.add_parser("resolve")
    skill_resolve.add_argument("--task", required=True)
    skill_resolve.set_defaults(func=cmd_skill_resolve)
    skill_pack = skill_sub.add_parser("pack")
    skill_pack_sub = skill_pack.add_subparsers(required=True)
    skill_pack_validate = skill_pack_sub.add_parser("validate")
    skill_pack_validate.add_argument("path")
    skill_pack_validate.set_defaults(func=cmd_skill_pack_validate)

    ingest = sub.add_parser("ingest")
    ingest_sub = ingest.add_subparsers(required=True)
    ingest_docs = ingest_sub.add_parser("docs")
    ingest_docs.add_argument("paths", nargs="+")
    ingest_docs.add_argument("--profile", default="default")
    ingest_docs.set_defaults(func=cmd_ingest_docs)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(required=True)
    validate = task_sub.add_parser("validate")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_task_validate)

    run = sub.add_parser("run")
    run.add_argument("task_path")
    run.add_argument("--profile")
    run.add_argument("--provider")
    run.add_argument(
        "--deny-provider-input",
        action="append",
        default=[],
        choices=[
            "public",
            "internal",
            "confidential",
            "restricted",
            "secret",
            "pii",
            "customer",
            "credential",
            "generated",
            "unknown",
        ],
    )
    run.add_argument("--auto-approve", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--runtime", choices=["native", "langgraph"], default="native")
    run.set_defaults(func=cmd_run)

    orchestration = sub.add_parser("orchestration")
    orchestration_sub = orchestration.add_subparsers(required=True)
    orchestration_run = orchestration_sub.add_parser(
        "run",
        description="Run a local policy-mediated orchestration spec.",
    )
    orchestration_run.add_argument("spec_path")
    orchestration_run.add_argument("--profile")
    orchestration_run.add_argument("--dry-run", action="store_true")
    orchestration_run.set_defaults(func=cmd_orchestration_run)
    orchestration_inspect = orchestration_sub.add_parser(
        "inspect",
        description="Inspect aggregate local orchestration evidence.",
    )
    orchestration_inspect.add_argument("orchestration_id")
    orchestration_inspect.set_defaults(func=cmd_orchestration_inspect)
    orchestration_approve = orchestration_sub.add_parser(
        "approve",
        description="Approve or deny a pending orchestration-level approval.",
    )
    orchestration_approve.add_argument("orchestration_id")
    orchestration_approve.add_argument("action_id")
    orchestration_approve.add_argument("--decision", choices=["approve", "deny"], required=True)
    orchestration_approve.add_argument("--actor", default="cli")
    orchestration_approve.add_argument("--reason")
    orchestration_approve.set_defaults(func=cmd_orchestration_approve)
    orchestration_resume = orchestration_sub.add_parser(
        "resume",
        description="Resume a paused local orchestration after supervisor approval.",
    )
    orchestration_resume.add_argument("orchestration_id")
    orchestration_resume.set_defaults(func=cmd_orchestration_resume)

    approve = sub.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("action_id")
    approve.add_argument("--decision", choices=["approve", "deny"], required=True)
    approve.add_argument("--actor", default="cli")
    approve.add_argument("--reason")
    approve.set_defaults(func=cmd_approve)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--token")
    serve.add_argument("--profile", default="default")
    serve.set_defaults(func=cmd_serve)

    commit = sub.add_parser("commit")
    commit_sub = commit.add_subparsers(required=True)
    commit_propose = commit_sub.add_parser("propose")
    commit_propose.add_argument("run_id")
    commit_propose.add_argument("--message", required=True)
    commit_propose.set_defaults(func=cmd_commit_propose)

    benchmark = sub.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(required=True)
    benchmark_list = benchmark_sub.add_parser("list")
    benchmark_list.set_defaults(func=cmd_benchmark_list)
    benchmark_show = benchmark_sub.add_parser("show")
    benchmark_show.add_argument("pack_id")
    benchmark_show.set_defaults(func=cmd_benchmark_show)
    benchmark_run = benchmark_sub.add_parser("run")
    benchmark_run.add_argument("pack_id")
    benchmark_run.add_argument("case_id")
    benchmark_run.set_defaults(func=cmd_benchmark_run)

    mcp = sub.add_parser(
        "mcp",
        description="Local MCP boundary inspection. V9 exposes resources/prompts only; no tools.",
    )
    mcp_sub = mcp.add_subparsers(required=True)
    mcp_serve = mcp_sub.add_parser("serve")
    mcp_serve.add_argument("--profile", default="default")
    mcp_serve.set_defaults(func=cmd_mcp_serve)
    mcp_resources = mcp_sub.add_parser("resources")
    mcp_resources_sub = mcp_resources.add_subparsers(required=True)
    mcp_resources_list = mcp_resources_sub.add_parser("list")
    mcp_resources_list.add_argument("--profile", default="default")
    mcp_resources_list.add_argument("--json", action="store_true")
    mcp_resources_list.set_defaults(func=cmd_mcp_resources_list)
    mcp_resources_read = mcp_resources_sub.add_parser("read")
    mcp_resources_read.add_argument("uri")
    mcp_resources_read.add_argument("--profile", default="default")
    mcp_resources_read.add_argument("--json", action="store_true")
    mcp_resources_read.set_defaults(func=cmd_mcp_resources_read)
    mcp_prompts = mcp_sub.add_parser("prompts")
    mcp_prompts_sub = mcp_prompts.add_subparsers(required=True)
    mcp_prompts_list = mcp_prompts_sub.add_parser("list")
    mcp_prompts_list.add_argument("--json", action="store_true")
    mcp_prompts_list.set_defaults(func=cmd_mcp_prompts_list)
    mcp_prompts_get = mcp_prompts_sub.add_parser("get")
    mcp_prompts_get.add_argument("name")
    mcp_prompts_get.add_argument("--arg", action="append", default=[])
    mcp_prompts_get.add_argument("--json", action="store_true")
    mcp_prompts_get.set_defaults(func=cmd_mcp_prompts_get)

    retrieval = sub.add_parser("retrieval")
    retrieval_sub = retrieval.add_subparsers(required=True)
    retrieval_index = retrieval_sub.add_parser("index")
    retrieval_index_sub = retrieval_index.add_subparsers(required=True)
    retrieval_index_build = retrieval_index_sub.add_parser("build")
    retrieval_index_build.add_argument("--index-id", required=True)
    retrieval_index_build.add_argument("--paths", nargs="+", required=True)
    retrieval_index_build.add_argument(
        "--mode",
        choices=["lexical", "dense", "hybrid"],
        default="lexical",
    )
    retrieval_index_build.add_argument(
        "--dense-backend", choices=["deterministic", "qdrant-local", "qdrant-server"]
    )
    retrieval_index_build.add_argument("--profile", default="default")
    retrieval_index_build.add_argument("--overwrite", action="store_true")
    retrieval_index_build.set_defaults(func=cmd_retrieval_index_build)
    retrieval_index_list = retrieval_index_sub.add_parser("list")
    retrieval_index_list.set_defaults(func=cmd_retrieval_index_list)
    retrieval_index_show = retrieval_index_sub.add_parser("show")
    retrieval_index_show.add_argument("index_id")
    retrieval_index_show.set_defaults(func=cmd_retrieval_index_show)
    retrieval_index_delete = retrieval_index_sub.add_parser("delete")
    retrieval_index_delete.add_argument("index_id")
    retrieval_index_delete.set_defaults(func=cmd_retrieval_index_delete)
    retrieval_query = retrieval_sub.add_parser("query")
    retrieval_query.add_argument("index_id")
    retrieval_query.add_argument("--query", required=True)
    retrieval_query.add_argument(
        "--mode",
        choices=["lexical", "dense", "hybrid"],
        default="lexical",
    )
    retrieval_query.add_argument("--k", type=int, default=5)
    retrieval_query.set_defaults(func=cmd_retrieval_query)
    retrieval_scorecard = retrieval_sub.add_parser("scorecard")
    retrieval_scorecard.add_argument("fixture_path")
    retrieval_scorecard.add_argument("--index-id", required=True)
    retrieval_scorecard.add_argument("--k", type=int, default=5)
    retrieval_scorecard.add_argument("--profile", default="default")
    retrieval_scorecard.add_argument("--output")
    retrieval_scorecard.set_defaults(func=cmd_retrieval_scorecard)

    inspect = sub.add_parser("inspect")
    inspect_sub = inspect.add_subparsers(required=True)
    inspect_run = inspect_sub.add_parser("run")
    inspect_run.add_argument("run_id")
    inspect_run.set_defaults(func=cmd_inspect_run)
    inspect_context = inspect_sub.add_parser("context")
    inspect_context.add_argument("run_id")
    inspect_context.set_defaults(func=cmd_inspect_context)
    inspect_policy = inspect_sub.add_parser("policy")
    inspect_policy.add_argument("profile")
    inspect_policy.set_defaults(func=cmd_inspect_policy)

    eval_cmd = sub.add_parser("eval")
    eval_cmd.set_defaults(func=cmd_eval)

    demo = sub.add_parser("demo")
    demo_sub = demo.add_subparsers(required=True)
    demo_provider_audit = demo_sub.add_parser("provider-audit")
    demo_provider_audit.set_defaults(func=cmd_demo_provider_audit)

    docs = sub.add_parser("docs")
    docs_sub = docs.add_subparsers(required=True)
    docs_check = docs_sub.add_parser("check")
    docs_check.add_argument("--output")
    docs_check.set_defaults(func=cmd_docs_check)

    migrate = sub.add_parser("migrate")
    migrate_sub = migrate.add_subparsers(required=True)
    migrate_schemas_cmd = migrate_sub.add_parser("schemas")
    migrate_schemas_cmd.add_argument("--write", action="store_true")
    migrate_schemas_cmd.add_argument("--output")
    migrate_schemas_cmd.set_defaults(func=cmd_migrate_schemas)

    export = sub.add_parser("export")
    export_sub = export.add_subparsers(required=True)
    export_json_cmd = export_sub.add_parser("json")
    export_json_cmd.add_argument("run_id")
    export_json_cmd.add_argument("--output")
    export_json_cmd.set_defaults(func=cmd_export_json)
    export_markdown_cmd = export_sub.add_parser("markdown")
    export_markdown_cmd.add_argument("run_id")
    export_markdown_cmd.add_argument("--output")
    export_markdown_cmd.set_defaults(func=cmd_export_markdown)
    sarif = export_sub.add_parser("sarif")
    sarif.add_argument("run_id")
    sarif.add_argument("--output")
    sarif.set_defaults(func=cmd_export_sarif)

    release = sub.add_parser("release")
    release_sub = release.add_subparsers(required=True)
    release_package_check = release_sub.add_parser("package-check")
    release_package_check.add_argument("--version")
    release_package_check.add_argument("--output")
    release_package_check.set_defaults(func=cmd_release_package_check)
    release_readiness = release_sub.add_parser("readiness")
    release_readiness.add_argument("--version")
    release_readiness.add_argument("--output")
    release_readiness.add_argument("--ci-run-id")
    release_readiness.set_defaults(func=cmd_release_readiness)

    doctor_cmd = sub.add_parser("doctor")
    doctor_cmd.set_defaults(func=cmd_doctor)
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config_path = write_default_config(root, force=args.force)
    (root / ".agent-harness" / "runs").mkdir(parents=True, exist_ok=True)
    (root / ".agent-harness" / "indexes").mkdir(parents=True, exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)
    policy_path = root / "policies" / "default.json"
    if args.force or not policy_path.exists():
        write_json(policy_path, DEFAULT_POLICY)
    docs_dir = root / "docs"
    docs_dir.mkdir(exist_ok=True)
    starter_doc = docs_dir / "agent-harness.md"
    if args.force or not starter_doc.exists():
        starter_doc.write_text(STARTER_DOC, encoding="utf-8")
    print(f"initialized {config_path}")
    return 0


def cmd_template_list(args: argparse.Namespace) -> int:
    del args
    for template in list_templates(Path.cwd()):
        print(
            f"{template.template_id}\t{template.version}\t{template.title}"
            f"\t{template.source_type}\t{template.compatibility_status}"
        )
    return 0


def cmd_template_show(args: argparse.Namespace) -> int:
    print(load_template(args.name, Path.cwd()).model_dump_json(indent=2))
    return 0


def cmd_template_validate(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    report = validate_templates(
        Path.cwd(),
        template_id=args.name,
        all_templates=args.all,
        output=output,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


def cmd_template_pack_validate(args: argparse.Namespace) -> int:
    report = validate_template_pack_path(Path(args.path))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


def cmd_template_apply(args: argparse.Namespace) -> int:
    target = args.target or args.destination or "."
    destination = Path(target).resolve()
    if args.dry_run or args.preview_diff:
        template = load_template(args.name, Path.cwd())
        diagnostics: list[dict[str, object]] = []
        if template.source_type == "bundled_pack":
            report = validate_bundled_template_pack(template.template_id)
            diagnostics = list(report["diagnostics"])
            if report["status"] != "passed":
                raise ValueError("template pack validation failed")
        profile = load_policy(Path.cwd(), args.profile)
        policy = PolicyEngine(Path.cwd(), profile)
        evidence = build_template_application_evidence(
            template,
            destination,
            policy,
            parameters=_template_parameters(template, args.param),
            mode="preview_diff" if args.preview_diff else "dry_run",
            diagnostics=diagnostics,
        )
        print(json.dumps(evidence, indent=2))
        return 0

    template = load_template(args.name, Path.cwd())
    apply_diagnostics: list[dict[str, object]] = []
    if template.source_type == "bundled_pack":
        report = validate_bundled_template_pack(template.template_id)
        apply_diagnostics = list(report["diagnostics"])
        if report["status"] != "passed":
            raise ValueError("template pack validation failed")
    summary = HarnessRuntime(Path.cwd()).apply_template(
        args.name,
        destination,
        profile_name=args.profile,
        force=args.force,
        parameters=_template_parameters(template, args.param),
        diagnostics=apply_diagnostics,
    )
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_skill_validate(args: argparse.Namespace) -> int:
    report = validate_skill(args.skill_id, Path.cwd())
    print(report.model_dump_json(indent=2))
    return 0 if report.status == "passed" else 1


def cmd_skill_list(args: argparse.Namespace) -> int:
    del args
    for diagnostic in skill_discovery_diagnostics(Path.cwd()):
        print(diagnostic["message"], file=sys.stderr)
    for skill in list_skills(Path.cwd()):
        print(
            f"{skill.skill_id}\t{skill.version}\t{skill.name}\t{skill.source_type}"
            f"\t{skill.compatibility_status}\t{skill.validation_status}\t{skill.description}"
        )
    return 0


def cmd_skill_show(args: argparse.Namespace) -> int:
    print(load_skill_detail(args.skill_id, Path.cwd()).model_dump_json(indent=2))
    return 0


def cmd_skill_render(args: argparse.Namespace) -> int:
    print(render_skill(args.skill_id, Path.cwd()), end="")
    return 0


def cmd_skill_resolve(args: argparse.Namespace) -> int:
    report = resolve_task_skills(Path(args.task), Path.cwd())
    print(report.model_dump_json(indent=2))
    return 0 if report.status == "passed" else 1


def cmd_skill_pack_validate(args: argparse.Namespace) -> int:
    report = validate_skill_pack_path(Path(args.path))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


def _template_parameters(template: TemplateDetail, values: list[str]) -> dict[str, str]:
    return resolve_template_parameters(template, _parse_template_parameters(values))


def _parse_template_parameters(values: list[str]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--param values must use key=value")
        key, parameter_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--param values must include a non-empty key")
        parameters[key] = parameter_value
    return parameters


def _parse_mcp_prompt_arguments(values: list[str]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--arg values must use key=value")
        key, parameter_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--arg values must include a non-empty key")
        parameters[key] = parameter_value
    return parameters


def cmd_ingest_docs(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    policy = PolicyEngine(root, load_policy(root, args.profile))
    index = ingest_documents(root, root / config.artifact_root, args.paths, policy)
    print(index)
    return 0


def cmd_task_validate(args: argparse.Namespace) -> int:
    task = load_public_model(Path(args.path), TaskSpec)
    print(task.model_dump_json(indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if args.runtime == "langgraph":
        from agent_harness.runtimes.langgraph_adapter import run_langgraph_adapter

        summary = run_langgraph_adapter(
            root,
            Path(args.task_path),
            profile_name=args.profile,
            provider_name=args.provider,
            deny_provider_input=args.deny_provider_input,
            auto_approve=args.auto_approve,
            dry_run=args.dry_run,
        )
    else:
        summary = HarnessRuntime(root).run_task(
            Path(args.task_path),
            profile_name=args.profile,
            provider_name=args.provider,
            deny_provider_input=args.deny_provider_input,
            auto_approve=args.auto_approve,
            dry_run=args.dry_run,
        )
    record_python_refactor_demo_if_applicable(
        root,
        Path(args.task_path),
        summary,
        dry_run=args.dry_run,
    )
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_orchestration_run(args: argparse.Namespace) -> int:
    summary = run_orchestration(
        Path.cwd(),
        Path(args.spec_path),
        profile_name=args.profile,
        dry_run=args.dry_run,
    )
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_orchestration_inspect(args: argparse.Namespace) -> int:
    payload = inspect_orchestration(Path.cwd(), args.orchestration_id)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_orchestration_approve(args: argparse.Namespace) -> int:
    approval = approve_orchestration_plan(
        Path.cwd(),
        args.orchestration_id,
        args.action_id,
        decision=args.decision,
        actor=args.actor,
        reason=args.reason,
    )
    print(approval.model_dump_json(indent=2))
    return 0


def cmd_orchestration_resume(args: argparse.Namespace) -> int:
    summary = resume_orchestration(Path.cwd(), args.orchestration_id)
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    approval = approve_action(
        Path.cwd(),
        args.run_id,
        args.action_id,
        decision=args.decision,
        actor=args.actor,
        reason=args.reason,
    )
    print(approval.model_dump_json(indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    if not _is_operator_loopback_host(args.host):
        print(
            f"error: serve host must be loopback-only; got {args.host!r}",
            file=sys.stderr,
        )
        return 1
    token = args.token or secrets.token_urlsafe(32)
    print(f"Operator server: http://{args.host}:{args.port}")
    print(f"Operator profile: {args.profile}")
    if args.token is None:
        print(f"Operator token: {token}")
    if _operator_dependencies_available():
        from agent_harness.operator import create_operator_app

        app = create_operator_app(
            project_root=Path.cwd(),
            token=token,
            profile=args.profile,
        )
        uvicorn = import_module("uvicorn")
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    print(
        "error: operator server requires FastAPI and uvicorn from agent-harness[operator]; "
        "install with `pip install agent-harness[operator]`",
        file=sys.stderr,
    )
    return 1


def cmd_commit_propose(args: argparse.Namespace) -> int:
    summary = HarnessRuntime(Path.cwd()).propose_git_commit(args.run_id, args.message)
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_benchmark_list(args: argparse.Namespace) -> int:
    del args
    for pack in list_benchmark_packs():
        print(f"{pack.pack_id}\t{pack.version}\t{pack.title}")
    return 0


def cmd_benchmark_show(args: argparse.Namespace) -> int:
    print(load_benchmark_pack(args.pack_id).model_dump_json(indent=2))
    return 0


def cmd_benchmark_run(args: argparse.Namespace) -> int:
    result = run_benchmark_case(Path.cwd(), args.pack_id, args.case_id)
    print(result.model_dump_json(indent=2))
    return 0


def cmd_mcp_resources_list(args: argparse.Namespace) -> int:
    payload = list_mcp_resources(Path.cwd(), profile=args.profile)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for resource in payload["resources"]:
            print(f"{resource['uri']}\t{resource['resource_type']}\t{resource['mime_type']}")
    return 0


def cmd_mcp_resources_read(args: argparse.Namespace) -> int:
    payload = read_mcp_resource(Path.cwd(), args.uri, profile=args.profile)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        content = payload["content"] if payload["content"] is not None else payload
        print(json.dumps(content, indent=2))
    return 1 if payload.get("denial_status") == "denied" else 0


def cmd_mcp_prompts_list(args: argparse.Namespace) -> int:
    payload = list_mcp_prompts(Path.cwd())
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for prompt in payload["prompts"]:
            print(f"{prompt['name']}\t{prompt['mime_type']}\t{prompt['description']}")
    return 0


def cmd_mcp_prompts_get(args: argparse.Namespace) -> int:
    payload = get_mcp_prompt(
        args.name,
        _parse_mcp_prompt_arguments(args.arg),
        project_root=Path.cwd(),
    )
    if args.json or payload.get("denial_status") == "denied":
        print(json.dumps(payload, indent=2))
    else:
        print(payload["messages"][0]["content"], end="")
    return 1 if payload.get("denial_status") == "denied" else 0


def cmd_mcp_serve(args: argparse.Namespace) -> int:
    if not _mcp_sdk_available():
        print(
            "error: MCP SDK is not installed; install with "
            "`pip install agent-harness[mcp]` or `uv sync --extra mcp`",
            file=sys.stderr,
        )
        return 1
    from agent_harness.mcp.server import run_mcp_stdio_server

    run_mcp_stdio_server(Path.cwd(), profile=args.profile)
    return 0


def cmd_retrieval_index_build(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    policy = PolicyEngine(root, load_policy(root, args.profile))
    manifest = build_retrieval_index(
        root,
        config,
        policy,
        args.index_id,
        args.paths,
        mode=args.mode,
        dense_backend=args.dense_backend,
        overwrite=args.overwrite,
    )
    payload = manifest.model_dump(mode="json")
    payload["manifest_path"] = (
        manifest_path(root, config, args.index_id).relative_to(root).as_posix()
    )
    print(json.dumps(payload, indent=2))
    return 0


def cmd_retrieval_index_list(args: argparse.Namespace) -> int:
    del args
    root = Path.cwd()
    config = load_config(root)
    print(json.dumps({"indexes": list_indexes(root, config)}, indent=2))
    return 0


def cmd_retrieval_index_show(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    manifest = load_index(root, config, args.index_id)
    print(manifest.model_dump_json(indent=2))
    return 0


def cmd_retrieval_index_delete(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    delete_index(root, config, args.index_id)
    print(json.dumps({"deleted": args.index_id}, indent=2))
    return 0


def cmd_retrieval_query(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    result = query_index(
        root,
        config,
        args.index_id,
        args.query,
        mode=args.mode,
        limit=args.k,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_retrieval_scorecard(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    policy = PolicyEngine(root, load_policy(root, args.profile))
    output = Path(args.output) if args.output else None
    result = run_retrieval_scorecard(
        root,
        config,
        policy,
        Path(args.fixture_path),
        args.index_id,
        k=args.k,
        output=output,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


def cmd_inspect_run(args: argparse.Namespace) -> int:
    config = load_config(Path.cwd())
    store = RunStore.open_existing(Path.cwd() / config.artifact_root, args.run_id)
    summary = store.read_data("summary.json")
    payload = {
        "events": store.events(),
        "summary": summary,
        "artifact_index": store.read_data("artifact-index.json"),
    }
    if (store.run_dir / "provider.json").exists():
        payload["provider"] = store.read_data("provider.json")
    if (store.run_dir / "provider_calls.json").exists():
        payload["provider_calls"] = store.read_data("provider_calls.json")
    if (store.run_dir / "provider_input.json").exists():
        payload["provider_input"] = store.read_data("provider_input.json")
    if (store.run_dir / "security_findings.json").exists():
        payload["security_findings"] = store.read_data("security_findings.json")
    if (store.run_dir / "runtime_adapter.json").exists():
        payload["runtime_adapter"] = store.read_data("runtime_adapter.json")
    if (store.run_dir / "schema_versions.json").exists():
        payload["schema_versions"] = store.read_data("schema_versions.json")
    if (store.run_dir / "skill_manifest.json").exists():
        payload["skill_manifest"] = store.read_data("skill_manifest.json")
    if (store.run_dir / "template_apply.json").exists():
        payload["template_apply"] = store.read_data("template_apply.json")
    if (store.run_dir / "git_commit.json").exists():
        payload["git_commit"] = store.read_data("git_commit.json")
    artifacts = summary.get("artifacts")
    workspace_relative = (
        artifacts.get("workspace_metadata") if isinstance(artifacts, dict) else None
    )
    if isinstance(workspace_relative, str):
        workspace_path = Path.cwd() / workspace_relative
        if workspace_path.exists():
            payload["workspace_metadata"] = load_json(workspace_path)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_inspect_context(args: argparse.Namespace) -> int:
    config = load_config(Path.cwd())
    store = RunStore.open_existing(Path.cwd() / config.artifact_root, args.run_id)
    print(json.dumps(store.read_data("context_manifest.json"), indent=2))
    return 0


def cmd_inspect_policy(args: argparse.Namespace) -> int:
    policy = load_policy(Path.cwd(), args.profile)
    print(policy.model_dump_json(indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    del args
    root = Path.cwd()
    results = run_builtin_evals(root)
    report = write_eval_report(root, results)
    print(json.dumps({"report": str(report)}, indent=2))
    return 0 if all(result.passed for result in results) else 1


def cmd_demo_provider_audit(args: argparse.Namespace) -> int:
    del args
    payload = run_provider_audit_demo(Path.cwd())
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "completed" else 1


def cmd_docs_check(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    report_path = write_docs_check_report(Path.cwd(), output)
    report = load_json(report_path)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "passed" else 1


def cmd_migrate_schemas(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    report = migrate_schemas(Path.cwd(), write=args.write, output=output)
    print(json.dumps(report, indent=2))
    return 0


def cmd_export_sarif(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    store = RunStore.open_existing(root / config.artifact_root, args.run_id)
    output = _export_output(root, config.artifact_root, args.run_id, args.output, ".sarif")
    print(export_sarif(store, output))
    return 0


def cmd_export_json(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    store = RunStore.open_existing(root / config.artifact_root, args.run_id)
    output = _export_output(root, config.artifact_root, args.run_id, args.output, ".json")
    print(export_json(store, output))
    return 0


def cmd_export_markdown(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    store = RunStore.open_existing(root / config.artifact_root, args.run_id)
    output = _export_output(root, config.artifact_root, args.run_id, args.output, ".md")
    print(export_markdown(store, output))
    return 0


def cmd_release_readiness(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    report = build_release_readiness_report(
        Path.cwd(),
        args.version,
        output=output,
        ci_run_id=args.ci_run_id,
    )
    print(json.dumps(report, indent=2))
    return 0


def cmd_release_package_check(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else None
    report = build_release_package_check_report(
        Path.cwd(),
        args.version,
        output=output,
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "passed" else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    del args
    ok, messages = doctor(Path.cwd())
    for message in messages:
        print(message)
    return 0 if ok else 1


def _export_output(
    root: Path, artifact_root: str, run_id: str, output: str | None, suffix: str
) -> Path:
    if output:
        return Path(output)
    return root / artifact_root / "exports" / f"{run_id}{suffix}"


def _is_operator_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _operator_dependencies_available() -> bool:
    return (
        importlib.util.find_spec("fastapi") is not None
        and importlib.util.find_spec("uvicorn") is not None
    )


def _mcp_sdk_available() -> bool:
    return importlib.util.find_spec("mcp") is not None
