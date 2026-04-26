from pathlib import Path


def eval_work_dir(project_root: Path, eval_id: str) -> Path:
    return project_root / ".agent-harness" / "eval-work" / eval_id
