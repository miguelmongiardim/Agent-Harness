from __future__ import annotations

import shutil
from pathlib import Path

from agent_harness.runtime import HarnessRuntime
from agent_harness.schemas import EvalResult, EvalSpec
from agent_harness.utils import now_utc, write_json


BUILTIN_EVALS = [
    EvalSpec(
        schema_version="eval.v1",
        eval_id="python-refactor-dry-run",
        title="Python refactor dry run produces approval artifact",
        task_path="examples/tasks/python_refactor.json",
        expected_status="dry_run",
        required_artifacts=["context_manifest", "events", "summary"],
    )
]


def run_builtin_evals(project_root: Path) -> list[EvalResult]:
    results: list[EvalResult] = []
    for spec in BUILTIN_EVALS:
        task_path = project_root / spec.task_path
        if not task_path.exists():
            results.append(EvalResult(eval_id=spec.eval_id, passed=False, message="task missing"))
            continue
        try:
            summary = HarnessRuntime(project_root).run_task(task_path, dry_run=True)
            missing = [name for name in spec.required_artifacts if name not in summary.artifacts]
            passed = summary.status == spec.expected_status and not missing
            results.append(
                EvalResult(
                    eval_id=spec.eval_id,
                    passed=passed,
                    message="passed" if passed else f"status={summary.status} missing={missing}",
                    artifacts=summary.artifacts,
                )
            )
        except Exception as exc:  # pragma: no cover - eval command reports exceptions as data
            results.append(EvalResult(eval_id=spec.eval_id, passed=False, message=str(exc)))
    return results


def write_eval_report(project_root: Path, results: list[EvalResult]) -> Path:
    output_dir = project_root / ".agent-harness" / "evals"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    output = output_dir / f"eval-{stamp}.json"
    write_json(output, {"results": [result.model_dump(mode="json") for result in results]})
    markdown = output.with_suffix(".md")
    lines = ["# Agent Harness Eval Report", ""]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {status}: {result.eval_id} - {result.message}")
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def scanner_report(project_root: Path) -> Path:
    reports = project_root / ".agent-harness" / "exports"
    reports.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "scanner_report.v1",
        "status": "report-only",
        "tools": {
            "ruff": bool(shutil.which("ruff")),
            "mypy": bool(shutil.which("mypy")),
        },
        "critical_findings": [],
    }
    output = reports / "scanner-report.json"
    write_json(output, report)
    return output
