from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from agent_harness.config import load_config, load_model, write_default_config
from agent_harness.defaults import DEFAULT_POLICY
from agent_harness.doctor import doctor
from agent_harness.evals import run_builtin_evals, scanner_report, write_eval_report
from agent_harness.exporters import export_json, export_markdown, export_sarif
from agent_harness.policy import PolicyEngine, load_policy
from agent_harness.retrieval import ingest_documents
from agent_harness.runtime import HarnessRuntime, approve_action
from agent_harness.schemas import TaskSpec
from agent_harness.storage import RunStore
from agent_harness.templates import list_templates, load_template
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
    template_apply = template_sub.add_parser("apply")
    template_apply.add_argument("name")
    template_apply.add_argument("--destination", default=".")
    template_apply.add_argument("--force", action="store_true")
    template_apply.add_argument("--profile", default="default")
    template_apply.set_defaults(func=cmd_template_apply)

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
    run.set_defaults(func=cmd_run)

    approve = sub.add_parser("approve")
    approve.add_argument("run_id")
    approve.add_argument("action_id")
    approve.add_argument("--decision", choices=["approve", "deny"], required=True)
    approve.add_argument("--actor", default="cli")
    approve.add_argument("--reason")
    approve.set_defaults(func=cmd_approve)

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
    for template in list_templates():
        print(f"{template.template_id}\t{template.version}\t{template.title}")
    return 0


def cmd_template_show(args: argparse.Namespace) -> int:
    print(load_template(args.name).model_dump_json(indent=2))
    return 0


def cmd_template_apply(args: argparse.Namespace) -> int:
    destination = Path(args.destination).resolve()
    summary = HarnessRuntime(Path.cwd()).apply_template(
        args.name,
        destination,
        profile_name=args.profile,
        force=args.force,
    )
    print(summary.model_dump_json(indent=2))
    return 0


def cmd_ingest_docs(args: argparse.Namespace) -> int:
    root = Path.cwd()
    config = load_config(root)
    policy = PolicyEngine(root, load_policy(root, args.profile))
    index = ingest_documents(root, root / config.artifact_root, args.paths, policy)
    print(index)
    return 0


def cmd_task_validate(args: argparse.Namespace) -> int:
    task = load_model(Path(args.path), TaskSpec)
    print(task.model_dump_json(indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    summary = HarnessRuntime(Path.cwd()).run_task(
        Path(args.task_path),
        profile_name=args.profile,
        provider_name=args.provider,
        deny_provider_input=args.deny_provider_input,
        auto_approve=args.auto_approve,
        dry_run=args.dry_run,
    )
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
    if (store.run_dir / "template_apply.json").exists():
        payload["template_apply"] = store.read_data("template_apply.json")
    artifacts = summary.get("artifacts")
    workspace_relative = (
        artifacts.get("workspace_metadata") if isinstance(artifacts, dict) else None
    )
    if isinstance(workspace_relative, str):
        workspace_path = Path.cwd() / workspace_relative
        if workspace_path.exists():
            payload["workspace_metadata"] = load_json(workspace_path)
    print(
        json.dumps(payload, indent=2)
    )
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
    scanner = scanner_report(root)
    scanner_data = load_json(scanner)
    print(json.dumps({"report": str(report), "scanner_report": str(scanner)}, indent=2))
    scanner_ok = scanner_data.get("status") != "failed"
    return 0 if scanner_ok and all(result.passed for result in results) else 1


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
