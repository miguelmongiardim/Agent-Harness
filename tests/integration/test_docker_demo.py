from __future__ import annotations

from pathlib import Path


def test_docker_golden_path_is_packaged_documented_and_ci_validated() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    docs = "\n".join(
        [
            Path("README.md").read_text(encoding="utf-8"),
            Path("docs/release-readiness.md").read_text(encoding="utf-8"),
        ]
    )

    assert "FROM python:3.12-slim" in dockerfile
    assert "python -m pip install --no-cache-dir ." in dockerfile
    assert 'CMD ["agent-harness", "doctor"]' in dockerfile
    assert "ENTRYPOINT" not in dockerfile

    for ignored in (".git", ".agent-harness", ".venv", ".venv-win", "dist", "build"):
        assert ignored in dockerignore

    assert "docker build -t agent-harness:local ." in docs
    assert "docker run --rm agent-harness:local agent-harness demo provider-audit" in docs
    assert "local/demo reproducibility" in docs
    assert "not production deployment" in docs

    assert "docker-demo:" in workflow
    assert "docker build -t agent-harness:local ." in workflow
    assert "docker run --rm agent-harness:local agent-harness demo provider-audit" in workflow
